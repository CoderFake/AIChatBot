"""
Department Service
Manages department CRUD operations with proper error handling and transaction management
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError

from models.database.tenant import Department, Tenant
from models.database.agent import Agent
from services.agents.agent_service import AgentService
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager

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
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create new department
        Raises exception on error for transaction rollback
        """
        try:
            result = await self.db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                logger.error(f"Tenant {tenant_id} not found")
                raise ValueError(f"Tenant {tenant_id} not found")
            
            existing_result = await self.db.execute(
                select(Department).where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Department.department_name == department_name
                    )
                )
            )
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                logger.error(f"Department '{department_name}' already exists in tenant {tenant_id}")
                raise ValueError(f"Department '{department_name}' already exists")
            
            department = Department(
                tenant_id=tenant_id,
                department_name=department_name,
                description=description,
                is_active=True
            )
            
            self.db.add(department)
            await self.db.flush() 
            
            result = {
                "id": str(department.id),
                "name": department.department_name,
                "description": department.description,
                "tenant_id": tenant_id,
                "tenant_name": tenant.tenant_name,
                "is_active": department.is_active,
                "created_at": department.created_at.isoformat() if department.created_at else None
            }
            
            logger.info(f"Created department '{department_name}' with ID {department.id}")
            return result
            
        except ValueError:
            # Re-raise validation errors
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating department '{department_name}': {e}")
            raise RuntimeError(f"Database error creating department: {e}")
        except Exception as e:
            logger.error(f"Failed to create department '{department_name}': {e}")
            raise RuntimeError(f"Failed to create department: {e}")
    
    async def create_department_with_agent_and_provider(
        self,
        tenant_id: str,
        department_name: str,
        agent_name: str,
        agent_description: str,
        provider_id: str,
        model_id: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        config_data: Optional[Dict[str, Any]] = None,
        department_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create department + agent + provider config in single transaction
        This is the main orchestrator method with transaction wrapper
        """
        try:
            # Start transaction
            logger.info(f"Starting transaction: create department '{department_name}' with agent '{agent_name}'")
            
            # Step 1: Create department
            dept_result = await self.create_department(
                tenant_id=tenant_id,
                department_name=department_name,
                description=department_description
            )
            logger.info(f"✓ Department created: {dept_result['id']}")
            
            # Step 2: Call AgentService to create agent with provider
            agent_result = await self.agent_service.create_agent_with_provider(
                tenant_id=tenant_id,
                department_id=dept_result['id'],
                agent_name=agent_name,
                description=agent_description,
                provider_id=provider_id,
                model_id=model_id,
                api_keys=api_keys,
                config_data=config_data
            )
            logger.info(f"✓ Agent with provider created: {agent_result['agent']['id']}")
            
            # Commit transaction
            await self.db.commit()
            logger.info(f"✓ Transaction committed successfully")
            
            # Return combined result
            return {
                "department": dept_result,
                "agent": agent_result['agent'],
                "provider_config": agent_result['provider_config'],
                "transaction_status": "success"
            }
            
        except (ValueError, RuntimeError) as e:
            # Business logic errors - rollback and re-raise
            await self.db.rollback()
            logger.error(f"Transaction rolled back due to business error: {e}")
            raise
        except SQLAlchemyError as e:
            # Database errors - rollback and raise RuntimeError
            await self.db.rollback()
            logger.error(f"Transaction rolled back due to database error: {e}")
            raise RuntimeError(f"Database error in transaction: {e}")
        except Exception as e:
            # Unexpected errors - rollback and raise RuntimeError
            await self.db.rollback()
            logger.error(f"Transaction rolled back due to unexpected error: {e}")
            raise RuntimeError(f"Unexpected error in transaction: {e}")
    
    async def get_department_by_id(self, department_id: str) -> Optional[Dict[str, Any]]:
        """
        Get department by ID
        """
        try:
            result = await self.db.execute(
                select(Department).where(Department.id == department_id)
            )
            department = result.scalar_one_or_none()
            
            if not department:
                logger.warning(f"Department {department_id} not found")
                return None
            
            # Get agent count
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
                "tenant_name": department.tenant.tenant_name if department.tenant else None,
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
        department_name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update department
        Raises exception on error for transaction rollback
        """
        try:
            result = await self.db.execute(
                select(Department).where(Department.id == department_id)
            )
            department = result.scalar_one_or_none()
            
            if not department:
                logger.error(f"Department {department_id} not found")
                raise ValueError(f"Department {department_id} not found")
            
            # Update fields if provided
            if department_name is not None:
                # Check for name conflicts
                existing_result = await self.db.execute(
                    select(Department).where(
                        and_(
                            Department.tenant_id == department.tenant_id,
                            Department.department_name == department_name,
                            Department.id != department_id
                        )
                    )
                )
                existing = existing_result.scalar_one_or_none()
                
                if existing:
                    logger.error(f"Department name '{department_name}' already exists")
                    raise ValueError(f"Department name '{department_name}' already exists")
                
                department.department_name = department_name
            
            if description is not None:
                department.description = description
            
            if is_active is not None:
                department.is_active = is_active
            
            await self.db.flush()
            
            result = {
                "id": str(department.id),
                "name": department.department_name,
                "description": department.description,
                "tenant_id": str(department.tenant_id),
                "is_active": department.is_active,
                "updated_at": department.updated_at.isoformat() if department.updated_at else None
            }
            
            logger.info(f"Updated department {department_id}")
            return result
            
        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating department {department_id}: {e}")
            raise RuntimeError(f"Database error updating department: {e}")
        except Exception as e:
            logger.error(f"Failed to update department {department_id}: {e}")
            raise RuntimeError(f"Failed to update department: {e}")
    
    async def delete_department(self, department_id: str, cascade: bool = False) -> bool:
        """
        Delete department
        Raises exception on error for transaction rollback
        """
        try:
            result = await self.db.execute(
                select(Department).where(Department.id == department_id)
            )
            department = result.scalar_one_or_none()
            
            if not department:
                logger.error(f"Department {department_id} not found")
                raise ValueError(f"Department {department_id} not found")
            
            # Check for agents if not cascade
            if not cascade:
                agent_result = await self.db.execute(
                    select(Agent).where(Agent.department_id == department_id)
                )
                agents = agent_result.scalars().all()
                agent_count = len(agents)
                
                if agent_count > 0:
                    logger.error(f"Cannot delete department {department_id}: has {agent_count} agents")
                    raise ValueError(f"Department has {agent_count} agents. Use cascade=True to delete all.")
            
            # Delete department (cascade handled by DB constraints)
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
                .where(Department.tenant_id == tenant_id)
                .order_by(Department.department_name)
            )
            departments = result.scalars().all()
            
            result_list = []
            for dept in departments:
                agent_result = await self.db.execute(
                    select(Agent).where(Agent.department_id == str(dept.id))
                )
                agents = agent_result.scalars().all()
                agent_count = len(agents)
                
                result_list.append({
                    "id": str(dept.id),
                    "name": dept.department_name,
                    "description": dept.description,
                    "tenant_id": str(dept.tenant_id),
                    "is_active": dept.is_active,
                    "agent_count": agent_count,
                    "created_at": dept.created_at.isoformat() if dept.created_at else None
                })
            
            logger.debug(f"Retrieved {len(result_list)} departments for tenant {tenant_id}")
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