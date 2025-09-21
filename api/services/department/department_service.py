"""
Department Service
Manages department CRUD operations with proper error handling and transaction management
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from models.database.tenant import Department, Tenant
from models.database.agent import Agent, AgentToolConfig
from services.agents.agent_service import AgentService
from common.types import DocumentAccessLevel, DocumentConstants
from utils.logging import get_logger

logger = get_logger(__name__)


class DepartmentService:
    """
    Service for department management operations
    Each method handles its own errors and raises exceptions for transaction rollback
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.agent_service = AgentService(db_session)
 
    async def create_department(
        self,
        tenant_id: str,
        department_name: str,
        agent_name: str,
        agent_description: str,
        provider_id: str,
        model_id: Optional[str] = None,
        config_data: Optional[Dict[str, Any]] = None,
        department_description: Optional[str] = None,
        tool_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create department + agent + provider config in single transaction
        This is the main orchestrator method with transaction wrapper
        """
        try:
            # Start transaction
            logger.info(f"Starting transaction: create department '{department_name}' with agent '{agent_name}'")
            
            # Step 1: Create department
            dept = Department(
                tenant_id=tenant_id,
                department_name=department_name,
                description=department_description,
                is_active=True
            )
            self.db.add(dept)
            await self.db.flush()

            # Get tenant name
            tenant_result = await self.db.execute(
                select(Tenant).where(Tenant.id == dept.tenant_id)
            )
            tenant_obj = tenant_result.scalar_one_or_none()
            tenant_name = tenant_obj.tenant_name if tenant_obj else None

            dept_result = {
                "id": str(dept.id),
                "department_name": dept.department_name,
                "description": dept.description,
                "tenant_id": str(dept.tenant_id),
                "tenant_name": tenant_name,
                "is_active": dept.is_active,
                "agent_count": 0,
                "created_at": dept.created_at.isoformat() if dept.created_at else None
            }

            agent_result = await self.agent_service.create_agent_with_provider(
                tenant_id=tenant_id,
                department_id=dept_result['id'],
                agent_name=agent_name,
                description=agent_description,
                provider_id=provider_id,
                model_id=model_id,
                config_data=config_data
            )

            tool_assignments = []
            if tool_ids:
                tool_assignments = await self._assign_tools_to_agent(
                    tenant_id=tenant_id,
                    agent_id=agent_result['agent']['id'],
                    tool_ids=tool_ids
                )
                logger.info(f"✓ Tools assigned to agent: {len(tool_assignments)} tools")

            from services.documents.document_service import DocumentService
            document_service = DocumentService(self.db)
            try:
                if not await document_service.get_root_folder(dept_result['id'], DocumentAccessLevel.PRIVATE.value):
                    await document_service.create_folder(
                        department_id=dept_result['id'],
                        folder_name=DocumentAccessLevel.PRIVATE.value,
                        folder_path=f"/{department_name}/Private",
                        parent_folder_id=None,
                        access_level=DocumentAccessLevel.PRIVATE.value,
                    )

                if not await document_service.get_root_folder(dept_result['id'], DocumentAccessLevel.PUBLIC.value):
                    await document_service.create_folder(
                        department_id=dept_result['id'],
                        folder_name=DocumentAccessLevel.PUBLIC.value,
                        folder_path=f"/{department_name}/Public",
                        parent_folder_id=None,
                        access_level=DocumentAccessLevel.PUBLIC.value,
                    )

                private_collection_name = DocumentConstants.private_collection_name(str(dept_result['id']))
                if not await document_service.get_collection(dept_result['id'], private_collection_name, DocumentAccessLevel.PRIVATE.value):
                    await document_service.create_collection(
                        department_id=dept_result['id'],
                        collection_name=private_collection_name,
                        collection_type=DocumentAccessLevel.PRIVATE.value,
                    )

                if not await document_service.get_collection(dept_result['id'], f"{dept_result['id']}-{DocumentAccessLevel.PUBLIC.value}", DocumentAccessLevel.PUBLIC.value):
                    await document_service.create_collection(
                        department_id=dept_result['id'],
                        collection_name=DocumentConstants.public_collection_name(str(dept_result['id'])),
                        collection_type=DocumentAccessLevel.PUBLIC.value,
                    )

            except Exception as e:
                raise RuntimeError(f"Failed to create default folders: {e}")

            await self.db.flush()
            await self.db.commit()
            dept_result["agent_count"] = 1

            return {
                "department": dept_result,
                "agent": agent_result['agent'],
                "tool_assignments": tool_assignments,
                "transaction_status": "success",
                "cache_invalidation": {
                    "tenant_id": tenant_id,
                    "entity_types": ['departments', 'agents', 'workflow_agents', 'provider_configs', 'provider_api_keys', 'tools']
                }
            }
            
        except (ValueError, RuntimeError) as e:
            logger.error(f"Transaction rolled back due to business error: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Transaction rolled back due to database error: {e}")
            raise RuntimeError(f"Database error in transaction: {e}")
        except Exception as e:
            logger.error(f"Transaction rolled back due to unexpected error: {e}")
            raise RuntimeError(f"Unexpected error in transaction: {e}")
    
    async def get_department(self, department_id: str) -> Optional[Dict[str, Any]]:
        """
        Get department by ID
        """
        try:
            result = await self.db.execute(
                select(Department).where(Department.id == department_id)
                .options(selectinload(Department.tenant))
            )
            department = result.scalar_one_or_none()
            
            if not department:
                logger.warning(f"Department {department_id} not found")
                return None
            
            agent_result = await self.db.execute(
                select(Agent).where(Agent.department_id == department_id)
            )
            agents = agent_result.scalars().all()
            agent_count = len(agents)
            
            return {
                "id": str(department.id),
                "name": department.department_name,
                "description": department.description,
                "tenant_id": str(department.tenant_id),
                "is_active": department.is_active,
                "agent_count": agent_count,
                "created_at": department.created_at.isoformat() if department.created_at else None
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting department {department_id}: {e}")
            raise RuntimeError(f"Database error getting department: {e}")
        except Exception as e:
            logger.error(f"Failed to get department {department_id}: {e}")
            raise RuntimeError(f"Failed to get department: {e}")
    
    async def update_department(
        self,
        department_id: str,
        tenant_id: str,
        department_name: str,
        agent_name: str,
        agent_description: str,
        provider_id: str,
        model_id: Optional[str] = None,
        config_data: Optional[Dict[str, Any]] = None,
        department_description: Optional[str] = None,
        tool_ids: Optional[List[str]] = None,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update department + agent + provider config in single transaction
        This is the main orchestrator method with transaction wrapper for updates
        """
        try:
            logger.info(f"Starting transaction: update department '{department_id}' with agent '{agent_name}'")

            result = await self.db.execute(
                select(Department).where(Department.id == department_id)
            )
            dept = result.scalar_one_or_none()
            if not dept:
                raise ValueError(f"Department {department_id} not found")

            dept.department_name = department_name
            if department_description is not None:
                dept.description = department_description
            await self.db.flush()

            # Get tenant name
            tenant_result = await self.db.execute(
                select(Tenant).where(Tenant.id == dept.tenant_id)
            )
            tenant_obj = tenant_result.scalar_one_or_none()
            tenant_name = tenant_obj.tenant_name if tenant_obj else None

            dept_result = {
                "id": str(dept.id),
                "department_name": dept.department_name,
                "description": dept.description,
                "tenant_id": str(dept.tenant_id),
                "tenant_name": tenant_name,
                "is_active": dept.is_active,
                "agent_count": 0,
                "created_at": dept.created_at.isoformat() if dept.created_at else None
            }
            logger.info(f"✓ Department updated: {dept_result['id']}")

            agent_result = await self.db.execute(
                select(Agent).where(Agent.department_id == department_id)
            )
            existing_agent = agent_result.scalar_one_or_none()

            if existing_agent and agent_name != existing_agent.agent_name:
                name_conflict_result = await self.db.execute(
                    select(Agent).where(
                        Agent.tenant_id == tenant_id,
                        Agent.agent_name == agent_name,
                        Agent.id != existing_agent.id
                    )
                )
                name_conflict = name_conflict_result.scalar_one_or_none()
                if name_conflict:
                    raise ValueError(f"Agent name '{agent_name}' already exists in tenant")

            if department_id != str(existing_agent.department_id if existing_agent else ""):
                dept_validation_result = await self.db.execute(
                    select(Department).where(
                        Department.id == department_id,
                        Department.tenant_id == tenant_id,
                        not Department.is_deleted
                    ).options(selectinload(Department.agent))
                )
                target_dept = dept_validation_result.scalar_one_or_none()
                if not target_dept:
                    raise ValueError("Target department not found")

                if target_dept.agent and (not existing_agent or str(target_dept.agent.id) != str(existing_agent.id)):
                    raise ValueError("Target department already has an agent")

            if existing_agent:
                logger.info(f"Found existing agent {existing_agent.id}, updating...")
                agent_result = await self.agent_service.update_agent_for_tenant_admin(
                    agent_id=str(existing_agent.id),
                    tenant_id=tenant_id,
                    department_id=department_id,
                    agent_name=agent_name,
                    description=agent_description,
                    provider_id=provider_id,
                    model_id=model_id
                )
                agent_id = str(existing_agent.id)
                logger.info(f"✓ Existing agent updated: {agent_id}")
            else:
                logger.info("No agent found for department, creating new agent...")
                agent_result = await self.agent_service.create_agent_with_provider(
                    tenant_id=tenant_id,
                    department_id=department_id,
                    agent_name=agent_name,
                    description=agent_description,
                    provider_id=provider_id,
                    model_id=model_id,
                    config_data=config_data
                )
                agent_id = agent_result['agent']['id']
                logger.info(f"✓ New agent created: {agent_id}")

            # Step 3: Update tool assignments
            tool_assignments = []
            if tool_ids is not None:
                await self.db.execute(
                    delete(AgentToolConfig).where(AgentToolConfig.agent_id == agent_id)
                )
                logger.info(f"✓ Removed existing tool assignments for agent {agent_id}")

                if tool_ids:
                    tool_assignments = await self._assign_tools_to_agent(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        tool_ids=tool_ids
                    )
                    logger.info(f"✓ New tools assigned to agent: {len(tool_assignments)} tools")

                from services.documents.document_service import DocumentService
                document_service = DocumentService(self.db)

                if not await document_service.get_root_folder(department_id, DocumentAccessLevel.PRIVATE.value):
                    await document_service.create_folder(
                        department_id=department_id,
                        folder_name=DocumentAccessLevel.PRIVATE.value,
                        folder_path=f"/{department_name}/Private",
                        parent_folder_id=None,
                        access_level=DocumentAccessLevel.PRIVATE.value,
                    )

                if not await document_service.get_root_folder(department_id, DocumentAccessLevel.PUBLIC.value):
                    await document_service.create_folder(
                        department_id=department_id,
                        folder_name=DocumentAccessLevel.PUBLIC.value,
                        folder_path=f"/{department_name}/Public",
                        parent_folder_id=None,
                        access_level=DocumentAccessLevel.PUBLIC.value,
                    )


                private_collection_name = DocumentConstants.private_collection_name(str(department_id))
                if not await document_service.get_collection(department_id, private_collection_name, DocumentAccessLevel.PRIVATE.value):
                    await document_service.create_collection(
                        department_id=department_id,
                        collection_name=private_collection_name,
                        collection_type=DocumentAccessLevel.PRIVATE.value,
                    )
                public_collection_name = DocumentConstants.public_collection_name(str(department_id))
                if not await document_service.get_collection(department_id, public_collection_name, DocumentAccessLevel.PUBLIC.value):
                    await document_service.create_collection(
                        department_id=department_id,
                        collection_name=public_collection_name,
                        collection_type=DocumentAccessLevel.PUBLIC.value,
                    )

            await self.db.flush()

            dept_result["agent_count"] = 1

            final_agent_result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
                .options(selectinload(Agent.provider))
            )
            final_agent = final_agent_result.scalar_one_or_none()

            await self.db.commit()

            result = {
                "department": dept_result,
                "agent": {
                    "id": str(final_agent.id),
                    "agent_name": final_agent.agent_name,
                    "description": final_agent.description,
                    "is_enabled": final_agent.is_enabled,
                    "provider_id": str(final_agent.provider_id) if final_agent.provider_id else None,
                    "provider_name": final_agent.provider.provider_name if final_agent.provider else None,
                    "model_id": str(final_agent.model_id) if final_agent.model_id else None,
                    "created_at": final_agent.created_at.isoformat() if final_agent.created_at else None
                } if final_agent else None,
                "tool_assignments": tool_assignments,
                "message": f"Department '{department_name}' updated successfully",
                "cache_invalidation": {
                    "tenant_id": tenant_id,
                    "entity_types": ['departments', 'agents', 'workflow_agents', 'provider_configs', 'provider_api_keys', 'tools']
                }
            }

            return result

        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error in update transaction: {e}")
            raise RuntimeError(f"Database error updating department: {e}")
        except Exception as e:
            logger.error(f"Failed to update department with agent: {e}")
            raise RuntimeError(f"Failed to update department: {e}")

    async def delete_department(self, department_id: str, cascade: bool = False) -> bool:
        """
        Delete department
        Raises exception on error for transaction rollback
        """
        try:
            result = await self.db.execute(
                select(Department).where(Department.id == department_id)
                .options(selectinload(Department.tenant))
            )
            department = result.scalar_one_or_none()
            
            if not department:
                logger.error(f"Department {department_id} not found")
                raise ValueError(f"Department {department_id} not found")
            
            if not cascade:
                agent_result = await self.db.execute(
                    select(Agent).where(Agent.department_id == department_id)
                )
                agents = agent_result.scalars().all()
                agent_count = len(agents)
                
                if agent_count > 0:
                    logger.error(f"Cannot delete department {department_id}: has {agent_count} agents")
                    raise ValueError(f"Department has {agent_count} agents. Use cascade=True to delete all.")
            
            await self.db.delete(department)
            await self.db.flush()
            
            logger.info(f"Deleted department {department_id} (cascade={cascade})")
            return True
            
        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting department {department_id}: {e}")
            raise RuntimeError(f"Database error deleting department: {e}")
        except Exception as e:
            logger.error(f"Failed to delete department {department_id}: {e}")
            raise RuntimeError(f"Failed to delete department: {e}")
    
    async def get_departments_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get all departments for a tenant
        """
        try:
            result = await self.db.execute(
                select(Department)
                .options(selectinload(Department.tenant))
                .where(Department.tenant_id == tenant_id)
                .order_by(Department.department_name)
            )
            departments = result.scalars().all()

            from models.database.user import User
            from models.database.provider import Provider, ProviderModel
            from models.database.agent import AgentToolConfig
            from models.database.tool import Tool
            
            result_list = []
            for dept in departments:
                agent_result = await self.db.execute(
                    select(Agent).where(Agent.department_id == str(dept.id))
                )
                agents = agent_result.scalars().all()
                agent_count = len(agents)
                
                user_result = await self.db.execute(
                    select(User).where(
                        and_(
                            User.department_id == str(dept.id),
                            User.role.in_(["dept_admin", "dept_manager"])
                        )
                    )
                )
                dept_users = user_result.scalars().all()
                user_count = len(dept_users)

                agent_data = None
                tool_assignments = []
                if agents:
                    first_agent = agents[0] 
                    
                   
                    provider_result = await self.db.execute(
                        select(Provider, ProviderModel)
                        .select_from(Agent)
                        .join(Provider, Agent.provider_id == Provider.id, isouter=True)
                        .join(ProviderModel, Agent.model_id == ProviderModel.id, isouter=True)
                        .where(Agent.id == first_agent.id)
                    )
                    provider_data = provider_result.first()

                    provider_name = provider_data.Provider.provider_name if provider_data and provider_data.Provider else None
                    model_name = provider_data.ProviderModel.model_name if provider_data and provider_data.ProviderModel else None

                    agent_data = {
                        "id": str(first_agent.id),
                        "agent_name": first_agent.agent_name,
                        "description": first_agent.description,
                        "is_enabled": first_agent.is_enabled,
                        "provider_id": str(first_agent.provider_id) if first_agent.provider_id else None,
                        "provider_name": provider_name,
                        "model_id": str(first_agent.model_id) if first_agent.model_id else None,
                        "model_name": model_name,
                        "created_at": first_agent.created_at.isoformat() if first_agent.created_at else None
                    }

                    tool_result = await self.db.execute(
                        select(AgentToolConfig, Tool)
                        .join(Tool, AgentToolConfig.tool_id == Tool.id, isouter=True)
                        .where(AgentToolConfig.agent_id == first_agent.id)
                    )
                    tool_data = tool_result.all()

                    for agent_tool_config, tool in tool_data:
                        if tool:
                            tool_assignments.append({
                                "tool_id": str(tool.id),
                                "tool_name": tool.tool_name,
                                "description": tool.description,
                                "status": "assigned"
                            })

                # Get tenant name
                tenant_result = await self.db.execute(
                    select(Tenant).where(Tenant.id == dept.tenant_id)
                )
                tenant_obj = tenant_result.scalar_one_or_none()
                tenant_name = tenant_obj.tenant_name if tenant_obj else None

                result_list.append({
                    "id": str(dept.id),
                    "department_name": dept.department_name,
                    "description": dept.description,
                    "tenant_id": str(dept.tenant_id),
                    "tenant_name": tenant_name,
                    "is_active": dept.is_active,
                    "agent_count": agent_count,
                    "user_count": user_count,
                    "agent": agent_data,
                    "tool_assignments": tool_assignments,
                    "created_at": dept.created_at.isoformat() if dept.created_at else None
                })
            
            return result_list
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting departments for tenant {tenant_id}: {e}")
            raise RuntimeError(f"Database error getting departments: {e}")
        except Exception as e:
            logger.error(f"Failed to get departments for tenant {tenant_id}: {e}")
            raise RuntimeError(f"Failed to get departments: {e}")
    
    async def validate_department_exists(self, department_id: str, tenant_id: Optional[str] = None) -> bool:
        """
        Validate department exists and optionally belongs to tenant
        """
        try:
            query = select(Department).where(Department.id == department_id)

            if tenant_id:
                query = query.where(Department.tenant_id == tenant_id)

            result = await self.db.execute(query)
            department = result.scalar_one_or_none()
            return department is not None

        except Exception as e:
            logger.error(f"Failed to validate department {department_id}: {e}")
            return False

    async def _assign_tools_to_agent(
        self,
        tenant_id: str,
        agent_id: str,
        tool_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Assign tools to agent during department creation
        """
        try:
            from models.database.agent import AgentToolConfig
            from services.tools.tool_service import ToolService

            assigned_tools = []

            tool_service = ToolService(self.db)
            tenant_tools = await tool_service.get_tools_for_tenant_admin(tenant_id)

            available_tools_map = {tool["id"]: tool for tool in tenant_tools if tool.get("is_enabled", False)}

            for tool_id in tool_ids:
                tool_info = available_tools_map.get(tool_id)
                if not tool_info:
                    logger.warning(f"Tenant {tenant_id} does not have access to tool {tool_id} or tool is disabled")
                    continue

                agent_tool_config = AgentToolConfig(
                    agent_id=agent_id,
                    tool_id=tool_id,
                    is_enabled=True,
                    config_data={}
                )
                self.db.add(agent_tool_config)

                assigned_tools.append({
                    "tool_id": tool_id,
                    "tool_name": tool_info["tool_name"],
                    "description": tool_info["description"],
                    "status": "assigned"
                })

            await self.db.flush()
            logger.info(f"Assigned {len(assigned_tools)} tools to agent {agent_id}")
            return assigned_tools

        except Exception as e:
            logger.error(f"Failed to assign tools to agent {agent_id}: {e}")
            raise RuntimeError(f"Failed to assign tools: {e}")

