'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FileText, Upload, Download, Trash2, Plus, File, Folder, MoreVertical, ChevronDown, ChevronRight } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from 'react-i18next'
import { apiService } from '@/lib/api/index'
import { useAuth } from '@/lib/auth-context'
import type { Department } from '@/types'

interface Document {
  id: string
  filename: string
  name: string
  file_path: string
  path_display?: string
  file_size: number
  content_type: string
  uploaded_by: string
  department_id?: string
  created_at: string
  updated_at?: string
  permissions?: {
    can_access: boolean
    reason: string
  }
  collection?: any
}

interface DocumentManagementProps {
  tenantId: string
}

export function DocumentManagement({ tenantId }: DocumentManagementProps) {
  const { toast } = useToast()
  const { t } = useTranslation()
  const { user, loading: authLoading, is_authenticated } = useAuth()
  const [documents, setDocuments] = useState<Document[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [folderLoading, setFolderLoading] = useState(false)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [selectedDepartment, setSelectedDepartment] = useState<string>('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const [folders, setFolders] = useState<any[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string>('')
  const [activeFolder, setActiveFolder] = useState<string>('')
  const [isFolderDialogOpen, setIsFolderDialogOpen] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [parentFolder, setParentFolder] = useState<string>('')
  const [isBatchUpload, setIsBatchUpload] = useState(false)
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false)
  const [renameItem, setRenameItem] = useState<{type: 'document' | 'folder', id: string, currentName: string} | null>(null)
  const [newItemName, setNewItemName] = useState('')
  const [batchUploading, setBatchUploading] = useState(false)
  const [pendingParentFolder, setPendingParentFolder] = useState<string>('')

  useEffect(() => {
    if (isFolderDialogOpen) {
      if (pendingParentFolder) {
        setParentFolder(pendingParentFolder)
        setPendingParentFolder('')
      } else if (activeFolder && !parentFolder) {
        setParentFolder(activeFolder)
      }
    } else if (!isFolderDialogOpen) {
      setParentFolder('')
      setPendingParentFolder('')
    }
  }, [isFolderDialogOpen, pendingParentFolder, activeFolder, parentFolder])

  const [contextMenu, setContextMenu] = useState<{
    x: number
    y: number
    type: 'folder' | 'document' | 'background'
    item?: any
  } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const batchFileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (tenantId) {
      loadData()
    }
  }, [tenantId])

  // Debug: Monitor folders state changes
  useEffect(() => {
    folders.forEach((folder, index) => {
      if (folder.type === 'access_level' && folder.children && folder.children.length > 0) {
        folder.children.forEach((child: any, childIndex: number) => {
        })
      }
    })
  }, [folders])

  const loadFolders = async (folderId?: string) => {
    try {
      const response = await apiService.documents.getFolders(folderId)

      if (response.success && response.data) {
        if (!folderId) {
          const departmentMap = new Map()

          response.data.forEach((folder: any) => {
            const pathParts = folder.folder_path.split('/')
            if (pathParts.length >= 2) {
              const departmentName = pathParts[0]
              const accessLevel = pathParts[1]

              if (!departmentMap.has(departmentName)) {
                departmentMap.set(departmentName, {
                  id: `dept_${departmentName}`,
                  name: departmentName,
                  type: 'department',
                  path: departmentName,
                  path_display: departmentName,
                  children: [],
                  isExpanded: false,
                  department_name: departmentName
                })
              }

              const department = departmentMap.get(departmentName)
              const accessLevelFolder = {
                id: folder.id,
                name: accessLevel,
                type: 'access_level',
                path: departmentName, // Important: use department name as path for matching
                path_display: `${departmentName}/${accessLevel}`,
                access_level: accessLevel.toLowerCase(),
                parent_folder_id: departmentName,
                children: [], 
                isExpanded: false,
                department_name: departmentName,
                documents: folder.documents || [],
                subfolders: folder.subfolders || []
              }

              department.children.push(accessLevelFolder)
            }
          })

          const departments = Array.from(departmentMap.values()).sort((a, b) =>
            a.name.localeCompare(b.name)
          )

          // Only update if folders actually changed
          setFolders(prevFolders => {
            if (JSON.stringify(prevFolders) === JSON.stringify(departments)) {
              return prevFolders // No change, return same reference
            }
            return departments
          })
        } else {
          const folderData = response.data[0] 
          const isDepartmentVirtual = folderId.startsWith('dept_')
          const pathParts = folderData.folder_path.split('/')
          const isAccessLevel = pathParts.length === 2

          if (isDepartmentVirtual) {
            const departmentName = folderId.replace('dept_', '')

            const accessLevelFolders: any[] = []

            if (response.data && Array.isArray(response.data)) {
              const deptAccessFolders = response.data.filter((f: any) =>
                f.folder_path.startsWith(departmentName)
              )

              deptAccessFolders.forEach((folder: any) => {
                const accessLevel = folder.folder_path.split('/')[1]
                accessLevelFolders.push({
                  id: folder.id,
                  name: accessLevel,
                  type: 'access_level',
                  path: folder.folder_path,
                  path_display: `${departmentName}/${accessLevel}`,
                  access_level: accessLevel.toLowerCase(),
                  parent_folder_id: folderId,
                  children: [],
                  isExpanded: false,
                  department_name: departmentName,
                  documents: folder.documents || [],
                  subfolders: folder.subfolders || []
                })
              })
            }

            setFolders(prev => prev.map(folder => {
              if (folder.id === folderId) {
                const updatedFolder = { ...folder, children: accessLevelFolders, isExpanded: true }
                return updatedFolder
              }
              return folder
            }))
          } else if (isAccessLevel) {
            const folderContents = [
              ...folderData.subfolders.map((sub: any) => ({
                id: sub.id,
                name: sub.folder_name,
                type: 'folder',
                path: sub.folder_path,
                path_display: sub.folder_path,
                access_level: sub.access_level || 'private',
                parent_folder_id: sub.parent_folder_id,
                children: (sub.subfolders || []).map((nestedSub: any) => ({
                  id: nestedSub.id,
                  name: nestedSub.folder_name,
                  type: 'folder',
                  path: nestedSub.folder_path,
                  path_display: nestedSub.folder_path,
                  access_level: nestedSub.access_level || 'private',
                  parent_folder_id: nestedSub.parent_folder_id,
                  children: [],
                  isExpanded: false,
                  created_at: nestedSub.created_at,
                  updated_at: nestedSub.updated_at,
                  documents: nestedSub.documents || [],
                  subfolders: nestedSub.subfolders || []
                })),
                isExpanded: false,
                created_at: sub.created_at,
                updated_at: sub.updated_at,
                documents: sub.documents || [],
                subfolders: sub.subfolders || []
              }))
            ]

            setFolders(prev => {
              const newFolders = prev.map(folder => {
                const isMatch = folder.id === folderId ||
                               folder.path === folderData.folder_path ||
                               (folder.type === 'access_level' &&
                                folder.name === folderData.folder_name &&
                                folderData.folder_path.startsWith(folder.path || ''))

                if (isMatch) {
                  const updatedFolder = {
                    ...folder,
                    children: folderContents,
                    isExpanded: true,
                    subfolders: folderContents
                  }
                  return updatedFolder
                }
                return folder
              })

              return newFolders
            })

            // Add documents to documents state
            const newDocuments = folderData.documents.map((doc: any) => ({
              id: doc.id,
              filename: doc.name || doc.filename,
              name: doc.name || doc.filename,
              file_path: `${folderData.folder_path}/${doc.name}`,
              path_display: `${folderData.folder_path}/${doc.name}`,
              file_size: 0,
              content_type: '',
              uploaded_by: '',
              department_id: folderData.folder_path.split('/')[0] || '',
              created_at: doc.created_at,
              updated_at: doc.updated_at,
              permissions: { can_access: true, reason: 'folder_access' }
            }))
            setDocuments(prev => [...prev, ...newDocuments])
          } else {
            const folderContents = [
              ...folderData.subfolders.map((sub: any) => ({
                id: sub.id,
                name: sub.folder_name,
                type: 'folder',
                path: sub.folder_path,
                path_display: sub.folder_path,
                access_level: sub.access_level || 'private',
                parent_folder_id: sub.parent_folder_id,
                children: (sub.subfolders || []).map((nestedSub: any) => ({
                  id: nestedSub.id,
                  name: nestedSub.folder_name,
                  type: 'folder',
                  path: nestedSub.folder_path,
                  path_display: nestedSub.folder_path,
                  access_level: nestedSub.access_level || 'private',
                  parent_folder_id: nestedSub.parent_folder_id,
                  children: [],
                  isExpanded: false,
                  created_at: nestedSub.created_at,
                  updated_at: nestedSub.updated_at,
                  documents: nestedSub.documents || [],
                  subfolders: nestedSub.subfolders || []
                })),
                isExpanded: false,
                created_at: sub.created_at,
                updated_at: sub.updated_at,
                documents: sub.documents || [],
                subfolders: sub.subfolders || []
              }))
            ]

            setFolders(prev => prev.map(folder => {
              if (folder.id === folderId) {
                return { ...folder, children: folderContents, isExpanded: true }
              }
              return folder
            }))

            const newDocuments = folderData.documents.map((doc: any) => ({
              id: doc.id,
              filename: doc.name || doc.filename,
              name: doc.name || doc.filename,
              file_path: `${folderData.folder_path}/${doc.name}`,
              path_display: `${folderData.folder_path}/${doc.name}`,
              file_size: 0,
              content_type: '',
              uploaded_by: '',
              department_id: folderData.folder_path.split('/')[0] || '', // department is first part
              created_at: doc.created_at,
              updated_at: doc.updated_at,
              permissions: { can_access: true, reason: 'folder_access' }
            }))
            setDocuments(prev => [...prev, ...newDocuments])
          }
        }
      }
    } catch (error) {
    } finally {
      setFolderLoading(false)
    }
  }


  const loadInitialFolders = async () => {
    try {
      const deptResponse = await apiService.departments.list(tenantId)
      setDepartments(deptResponse || [])
    } catch (deptError) {
      setDepartments([])
    }

    try {
      setActiveFolder('')
      setDocuments([])
      await loadFolders()
      
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load folders",
        variant: "destructive",
      })
    }
  }

  const loadData = async () => {
    try {
      setLoading(true)
      await loadInitialFolders()
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load data",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setSelectedFile(file)
    }
  }

  const handleBatchFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || [])
    if (files.length > 0) {
      setSelectedFiles(files)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    try {
      setUploading(true)

      let finalFileName = selectedFile.name
      const existingFiles = documents.filter(doc =>
        doc.file_path.includes('/') &&
        doc.file_path.split('/').pop() === selectedFile.name
      )

      if (existingFiles.length > 0) {
        const nameParts = selectedFile.name.split('.')
        const baseName = nameParts.slice(0, -1).join('.')
        const extension = nameParts[nameParts.length - 1]

        let counter = 1
        while (documents.some(doc => doc.filename === `${baseName}${counter}.${extension}`)) {
          counter++
        }
        finalFileName = `${baseName}${counter}.${extension}`
      }

      const response = await apiService.documents.upload(selectedFile, {
        folder_id: selectedFolder || undefined,
        title: finalFileName,
      })

      if (response.success && response.document_id) {
        const newDocument = {
          id: response.document_id,
          filename: finalFileName,
          name: finalFileName,
          file_path: selectedFolder ? `${selectedFolder}/${finalFileName}` : finalFileName,
          path_display: selectedFolder ? `${selectedFolder}/${finalFileName}` : finalFileName,
          file_size: selectedFile.size,
          content_type: selectedFile.type,
          uploaded_by: user?.id || '',
          department_id: user?.department_id || '',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          permissions: { can_access: true, reason: 'upload' }
        }

        setDocuments(prev => [...prev, newDocument])

        if (selectedFolder) {
          setFolders(prev => prev.map(folder => {
            if (folder.id === selectedFolder) {
              return {
                ...folder,
                documents: [...(folder.documents || []), newDocument]
              }
            }
            return folder
          }))
        }
      }

      toast({
        title: "Success",
        description: "Document uploaded successfully",
      })

      setIsUploadDialogOpen(false)
      setSelectedFile(null)
      setSelectedFolder('')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to upload document",
        variant: "destructive",
      })
    } finally {
      setUploading(false)
    }
  }

  const handleBatchUpload = async () => {
    if (!selectedFiles.length) return

    try {
      setBatchUploading(true)

      // Handle duplicate file names for each file
      const processedFiles: File[] = []
      for (const file of selectedFiles) {
        let finalFileName = file.name
        const existingFiles = documents.filter(doc =>
          doc.file_path.includes('/') &&
          doc.file_path.split('/').pop() === file.name
        )

        if (existingFiles.length > 0) {
          const nameParts = file.name.split('.')
          const baseName = nameParts.slice(0, -1).join('.')
          const extension = nameParts[nameParts.length - 1]

          let counter = 1
          while (documents.some(doc => doc.filename === `${baseName}${counter}.${extension}`) ||
                 processedFiles.some(f => f.name === `${baseName}${counter}.${extension}`)) {
            counter++
          }
          finalFileName = `${baseName}${counter}.${extension}`
        }

        const renamedFile = new (File as any)([file], finalFileName, { type: file.type })
        processedFiles.push(renamedFile)
      }

      const response = await apiService.documents.uploadBatch(processedFiles, {
        folder_id: selectedFolder || undefined,
      })

      if (response.success) {
        const newDocuments = processedFiles.map((file, index) => ({
          id: `temp_${Date.now()}_${index}`, // Temporary ID until we get real response
          filename: file.name,
          name: file.name,
          file_path: selectedFolder ? `${selectedFolder}/${file.name}` : file.name,
          path_display: selectedFolder ? `${selectedFolder}/${file.name}` : file.name,
          file_size: file.size,
          content_type: file.type,
          uploaded_by: user?.id || '',
          department_id: user?.department_id || '',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          permissions: { can_access: true, reason: 'batch_upload' }
        }))

        // Add to documents state
        setDocuments(prev => [...prev, ...newDocuments])

        // Update folder's documents if uploaded to a folder
        if (selectedFolder) {
          setFolders(prev => prev.map(folder => {
            if (folder.id === selectedFolder) {
              return {
                ...folder,
                documents: [...(folder.documents || []), ...newDocuments]
              }
            }
            return folder
          }))
        }
      }

      toast({
        title: "Success",
        description: `Successfully uploaded ${selectedFiles.length} documents`,
      })

      setIsUploadDialogOpen(false)
      setSelectedFiles([])
      setSelectedFolder('')
      setIsBatchUpload(false)
      if (batchFileInputRef.current) {
        batchFileInputRef.current.value = ''
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to upload documents",
        variant: "destructive",
      })
    } finally {
      setBatchUploading(false)
    }
  }

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return

    try {
      const departmentId = user?.role === 'ADMIN' ? user?.department_id : undefined
      const response = await apiService.documents.createFolder(
        newFolderName.trim(),
        activeFolder || undefined,
        departmentId
      )

      if (response.success && response.data) {
        const newFolderData = response.data

        const newFolder = {
          id: newFolderData.id,
          name: newFolderData.folder_name,
          type: 'folder',
          path: newFolderData.folder_path,
          path_display: newFolderData.folder_path,
          parent_folder_id: activeFolder,
          children: [],
          isExpanded: false,
          created_at: newFolderData.created_at,
          updated_at: newFolderData.updated_at,
          documents: [],
          subfolders: []
        }

        setFolders(prev => prev.map(folder => {
          if (folder.id === activeFolder) {
            return {
              ...folder,
              children: [...(folder.children || []), newFolder],
              subfolders: [...(folder.subfolders || []), newFolder]
            }
          }
          return folder
        }))
      }

      toast({ title: 'Success', description: 'Folder created successfully' })
      setIsFolderDialogOpen(false)
      setNewFolderName('')
      setParentFolder('')
      setPendingParentFolder('')
    } catch (error) {
      toast({ title: 'Error', description: 'Failed to create folder', variant: 'destructive' })
    }
  }

  const handleDelete = async (documentId: string) => {
    try {
      setDeleting(documentId)
      await apiService.documents.delete(documentId)

      setDocuments(prev => prev.filter(doc => doc.id !== documentId))

      setFolders(prev => prev.map(folder => ({
        ...folder,
        documents: folder.documents?.filter((doc: any) => doc.id !== documentId) || []
      })))

      toast({
        title: "Success",
        description: "Document deleted successfully",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete document",
        variant: "destructive",
      })
    } finally {
      setDeleting(null)
    }
  }

  const handleContextMenu = (event: React.MouseEvent, type: 'folder' | 'document' | 'background', item?: any) => {
    event.preventDefault()
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      type,
      item
    })
  }

  const handleFolderClick = async (folder: any) => {
    setActiveFolder(folder.id)

    if (!folder.isExpanded) {
      setFolderLoading(true)

      if (folder.type === 'department') {
        const departmentName = folder.department_name

        if (!folder.children || folder.children.length === 0) {
          await loadFolders(folder.id)
        } else {
          setFolders(prev => prev.map(f => {
            if (f.id === folder.id) {
              return {
                ...f,
                isExpanded: true
              }
            }
            return f
          }))
          setFolderLoading(false)
        }
      } else if (folder.type === 'access_level') {
        const currentFolder = folders.find(f => f.id === folder.id)

        const hasChildren = currentFolder && currentFolder.children && currentFolder.children.length > 0

        if (!hasChildren) {
          try {
            await loadFolders(folder.id)
          } catch (error) {
          }
        }
      } else {
        await loadFolders(folder.id)
      }
    } else {
      setFolders(prev => prev.map(f =>
        f.id === folder.id
          ? { ...f, isExpanded: false }
          : f
      ))

      setDocuments(prev => prev.filter(doc => {
        if (folder.type === 'access_level' || folder.type === 'folder') {
          return !doc.file_path.startsWith(folder.path + '/')
        }
        // For department folders, clear all documents in child folders
        return !doc.file_path.includes(`/${folder.name}/`)
      }))
    }
  }

  const renderFolderTree = (folder: any, level: number = 0) => {
    const hasChildren = folder.children && folder.children.length > 0
    const isExpanded = folder.isExpanded
    const isActive = activeFolder === folder.id

    const canExpand = folder.type === 'department' ||
                     folder.type === 'access_level' ||
                     folder.type === 'folder' ||
                     (hasChildren && folder.children.some((child: any) => child.type === 'folder' || child.type === 'access_level'))


    return (
      <div key={`${folder.type}-${folder.id}-${level}`} className="group">
        <div
          className={`flex items-center gap-2 px-3 py-2 hover:bg-[#f4f4f4] cursor-pointer text-sm border-b border-border/50 last:border-b-0 transition-colors duration-150 ${
            level > 0 ? 'ml-4' : ''
          } ${
            isActive ? 'bg-blue-50 border-blue-200 text-blue-700 font-medium' : 'text-gray-700'
          }`}
          title={folder.path_display || folder.path || folder.name}
          onContextMenu={(e) => {
            e.preventDefault()
            e.stopPropagation()
            handleContextMenu(e, 'folder', folder)
          }}
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            handleFolderClick(folder)
          }}
        >
          {/* Expand/Collapse Icon */}
          {canExpand ? (
            <div
              className="flex-shrink-0 w-4 h-4 flex items-center justify-center cursor-pointer"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                handleFolderClick(folder)
              }}
            >
              {isExpanded ? (
                <ChevronDown className="w-3 h-3 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-3 h-3 text-muted-foreground" />
              )}
            </div>
          ) : (
            <div className="flex-shrink-0 w-4 h-4"></div> // Placeholder for alignment
          )}

          {/* Folder Icon */}
          <div className="flex-shrink-0 w-4 h-4 flex items-center justify-center">
            <Folder className="w-4 h-4 text-yellow-500" />
          </div>

          {/* Name */}
          <span className="flex-1 truncate">
            {folder.type === 'department'
              ? folder.name
              : folder.type === 'access_level'
              ? folder.name
              : folder.name || folder.filename || folder.folder_name
            }
            {hasChildren && folder.type !== 'department' && (
              <span className="ml-1 text-xs text-muted-foreground">
                ({folder.children.length})
              </span>
            )}
          </span>

          {/* Context Menu Trigger */}
          <div
            className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
            onClick={(e) => {
              e.stopPropagation()
              handleContextMenu(e, 'folder', folder)
            }}
          >
            <MoreVertical className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </div>
        </div>

        {/* Render children if expanded */}
        {isExpanded && hasChildren && (
          <div>
            {(() => {
              return folder.children.map((child: any, index: number) => {
                return renderFolderTree(child, level + 1)
              })
            })()}
          </div>
        )}
      </div>
    )
  }

  const handleContextMenuAction = (action: string) => {
    if (!contextMenu) return

    switch (action) {
      case 'newFolder':
        if (activeFolder) {
          setPendingParentFolder(activeFolder)
          setIsFolderDialogOpen(true)
        } else if (contextMenu.item && contextMenu.item.type === 'folder') {
          setPendingParentFolder(contextMenu.item.id)
          setIsFolderDialogOpen(true)
        } else {
          toast({
            title: 'Cannot Create Folder',
            description: 'Please select a parent folder first',
            variant: 'destructive',
          })
        }
        break
      case 'uploadDocument':
        if (activeFolder) {
          setSelectedFolder(activeFolder)
        } else if (contextMenu.item) {
          if (contextMenu.item.type === 'access_level' || contextMenu.item.type === 'folder') {
            setSelectedFolder(contextMenu.item.id)
          } else if (contextMenu.item.type === 'department') {
            setSelectedFolder(`pub_${contextMenu.item.id}`)
          }
        }
        setIsBatchUpload(true)
        setIsUploadDialogOpen(true)
        break
      case 'open':
        if (contextMenu.type === 'document' && contextMenu.item) {
          const downloadUrl = `/api/v1/documents/download/${contextMenu.item.id}`
          const link = document.createElement('a')
          link.href = downloadUrl
          link.download = contextMenu.item.name || `document_${contextMenu.item.id}`
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)

          toast({
            title: 'Download started',
            description: `Downloading ${contextMenu.item.filename}`,
          })
        } else if (contextMenu.type === 'folder' && contextMenu.item) {
          toast({
            title: 'Folder opened',
            description: `Navigated to ${contextMenu.item.name}`,
          })
        }
        break
      case 'download':
        if (contextMenu.type === 'document' && contextMenu.item) {
          const downloadUrl = `/api/v1/documents/download/${contextMenu.item.id}`
          const link = document.createElement('a')
          link.href = downloadUrl
          link.download = contextMenu.item.name || `document_${contextMenu.item.id}`
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)

          toast({
            title: 'Download started',
            description: `Downloading ${contextMenu.item.filename}`,
          })
        }
        break
      case 'refresh':
        loadData()
        toast({
          title: 'Refreshed',
          description: 'Document list has been refreshed',
        })
        break
      case 'rename':
        if (contextMenu.item) {
          const itemName = contextMenu.item.name || contextMenu.item.filename || contextMenu.item.folder_name

          if (contextMenu.type === 'folder' && (itemName === 'Public' || itemName === 'Private')) {
            toast({
              title: 'Cannot Rename',
              description: 'System folders (Public/Private) cannot be renamed',
              variant: 'destructive',
            })
          } else {
            setRenameItem({
              type: contextMenu.type as 'document' | 'folder',
              id: contextMenu.item.id,
              currentName: itemName
            })
            setNewItemName(itemName)
            setIsRenameDialogOpen(true)
          }
        }
        break
      case 'delete':
        if (contextMenu.type === 'document' && contextMenu.item) {
          handleDelete(contextMenu.item.id)
        } else if (contextMenu.type === 'folder' && contextMenu.item) {
          const folderName = contextMenu.item.name || contextMenu.item.folder_name
          if (folderName === 'Public' || folderName === 'Private') {
            toast({
              title: 'Cannot Delete',
              description: 'System folders (Public/Private) cannot be deleted',
              variant: 'destructive',
            })
          } else {
            handleDeleteFolder(contextMenu.item.id)
          }
        }
        break
    }

    setContextMenu(null)
  }

  const handleRename = async () => {
    if (!renameItem || !newItemName.trim()) return

    try {
      if (renameItem.type === 'document') {
        await apiService.documents.renameDocument(renameItem.id, newItemName.trim())

        // Update document name in local state
        setDocuments(prev => prev.map(doc =>
          doc.id === renameItem.id
            ? { ...doc, filename: newItemName.trim(), name: newItemName.trim() }
            : doc
        ))

        // Also update in folder's documents
        setFolders(prev => prev.map(folder => ({
          ...folder,
          documents: folder.documents?.map((doc: any) =>
            doc.id === renameItem.id
              ? { ...doc, filename: newItemName.trim(), name: newItemName.trim() }
              : doc
          ) || []
        })))

        toast({
          title: 'Success',
          description: 'Document renamed successfully',
        })
      } else if (renameItem.type === 'folder') {
        await apiService.documents.renameFolder(renameItem.id, newItemName.trim())

        // Update folder name in local state
        setFolders(prev => prev.map(folder =>
          folder.id === renameItem.id
            ? { ...folder, name: newItemName.trim() }
            : folder
        ))

        toast({
          title: 'Success',
          description: 'Folder renamed successfully',
        })
      }

      setIsRenameDialogOpen(false)
      setRenameItem(null)
      setNewItemName('')
    } catch (error) {
      toast({
        title: 'Error',
        description: `Failed to rename ${renameItem.type}`,
        variant: 'destructive',
      })
    }
  }

  const handleDeleteFolder = async (folderId: string) => {
    try {
      await apiService.documents.deleteFolder(folderId)
      toast({
        title: "Success",
        description: "Folder deleted successfully",
      })
      loadData()
    } catch (error) {
      toast({
        title: "Error", 
        description: "Failed to delete folder",
        variant: "destructive",
      })
    }
  }

  const closeContextMenu = () => {
    setContextMenu(null)
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase()
    switch (ext) {
      case 'pdf':
        return '📄'
      case 'doc':
      case 'docx':
        return '📝'
      case 'xls':
      case 'xlsx':
        return '📊'
      case 'ppt':
      case 'pptx':
        return '📈'
      case 'txt':
        return '📃'
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
        return '🖼️'
      default:
        return '📄'
    }
  }

  if (authLoading || !is_authenticated) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
        <p className="mt-4 text-muted-foreground">Loading user information...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6" onContextMenu={(e) => handleContextMenu(e, 'background')} onClick={closeContextMenu}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Document Management</h1>
          <p className="text-muted-foreground">
            Upload, organize, and manage your organization's documents
          </p>
        </div>

        <div className="flex gap-2">
          <Dialog open={isUploadDialogOpen} onOpenChange={setIsUploadDialogOpen}>
            <DialogTrigger asChild>
              <Button
                className="gap-2"
                onClick={() => {
                  setIsBatchUpload(false)
                  if (activeFolder) {
                    setSelectedFolder(activeFolder)
                  }
                }}
              >
                <Upload className="h-4 w-4" />
                Upload Document
              </Button>
            </DialogTrigger>

            <DialogTrigger asChild>
              <Button
                variant="outline"
                className="gap-2"
                onClick={() => {
                  setIsBatchUpload(true)
                  if (activeFolder) {
                    setSelectedFolder(activeFolder)
                  }
                }}
              >
                <Upload className="h-4 w-4" />
                Batch Upload
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{isBatchUpload ? 'Batch Upload Documents' : 'Upload Document'}</DialogTitle>
                <DialogDescription>
                  {isBatchUpload
                    ? 'Upload multiple documents at once to your organization'
                    : 'Upload a document to your organization'
                  }
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="file-upload">
                    {isBatchUpload ? 'Files (Max 10 files)' : 'File'}
                  </Label>
                  <Input
                    id="file-upload"
                    type="file"
                    ref={isBatchUpload ? batchFileInputRef : fileInputRef}
                    onChange={isBatchUpload ? handleBatchFileSelect : handleFileSelect}
                    accept=".pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif"
                    multiple={isBatchUpload}
                  />
                  {isBatchUpload ? (
                    selectedFiles.length > 0 && (
                      <div className="text-sm text-muted-foreground">
                        <p>Selected {selectedFiles.length} files:</p>
                        <ul className="mt-1 max-h-32 overflow-y-auto space-y-1">
                          {selectedFiles.map((file, index) => (
                            <li key={index} className="flex items-center justify-between bg-muted/50 rounded px-2 py-1">
                              <span className="text-sm truncate flex-1">{file.name} ({formatFileSize(file.size)})</span>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                                onClick={() => {
                                  setSelectedFiles(prev => prev.filter((_, i) => i !== index))
                                }}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )
                  ) : (
                    selectedFile && (
                      <p className="text-sm text-muted-foreground">
                        Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                      </p>
                    )
                  )}
                </div>
                {/* Show selected folder (from active folder) */}
                {selectedFolder && folders.length > 0 && (
                  <div className="grid gap-2">
                    <Label>Upload to Folder</Label>
                    <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
                      <Folder className="w-4 h-4 text-yellow-500" />
                      <span className="text-sm">
                        {folders.find(f => f.id === selectedFolder)?.name || 'Active folder'}
                      </span>
                    </div>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsUploadDialogOpen(false)
                    setSelectedFile(null)
                    setSelectedFiles([])
                    setSelectedDepartment('')
                    setSelectedFolder('')
                    setIsBatchUpload(false)
                    if (fileInputRef.current) {
                      fileInputRef.current.value = ''
                    }
                    if (batchFileInputRef.current) {
                      batchFileInputRef.current.value = ''
                    }
                  }}
                  disabled={uploading || batchUploading}
                >
                  Cancel
                </Button>
                <Button
                  onClick={isBatchUpload ? handleBatchUpload : handleUpload}
                  disabled={
                    (isBatchUpload ? selectedFiles.length === 0 : !selectedFile) ||
                    uploading ||
                    batchUploading
                  }
                >
                  {uploading || batchUploading ? 'Uploading...' : isBatchUpload ? `Upload ${selectedFiles.length} Files` : 'Upload'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={isFolderDialogOpen} onOpenChange={setIsFolderDialogOpen}>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                className="gap-2"
                disabled={!activeFolder}
                title={!activeFolder ? 'Select a folder first to create subfolder' : ''}
                onClick={() => {
                  if (activeFolder) {
                    setPendingParentFolder(activeFolder)
                  } else {
                    setPendingParentFolder('')
                  }
                }}
              >
                <Plus className="h-4 w-4" />
                New Folder
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Folder</DialogTitle>
                <DialogDescription>Create a new folder</DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="folder-name">Folder Name</Label>
                  <Input
                    id="folder-name"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                  />
                </div>


                {/* Show parent folder info */}
                {folders.length > 0 && (parentFolder || pendingParentFolder || activeFolder) && (
                  <div className="grid gap-2">
                    <Label>Parent Folder</Label>
                    <div className="flex items-center gap-2 p-2 bg-muted rounded-md">
                      <Folder className="w-4 h-4 text-yellow-500" />
                      <span
                        className="text-sm"
                        data-id={(() => {
                          const folderId = parentFolder || pendingParentFolder || activeFolder;
                          return folderId;
                        })()}
                      >
                        {(() => {
                          const folderId = parentFolder || pendingParentFolder || activeFolder;

                          const findFolderInTree = (tree: any[]): any => {
                            for (const item of tree) {
                              if (item.id === folderId) return item
                              if (item.children) {
                                const found = findFolderInTree(item.children)
                                if (found) return found
                              }
                            }
                            return null
                          }

                          const folder = findFolderInTree(folders)
                          return folder?.name || folder?.path_display || 'Root';
                        })()}
                      </span>
                    </div>
                  </div>
                )}

              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => {
                  setIsFolderDialogOpen(false)
                  setNewFolderName('')
                  setParentFolder('')
                  setPendingParentFolder('')
                }}>
                  Cancel
                </Button>
                <Button onClick={handleCreateFolder} disabled={!newFolderName.trim()}>
                  Create
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Rename Dialog */}
          <Dialog open={isRenameDialogOpen} onOpenChange={setIsRenameDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Rename {renameItem?.type}</DialogTitle>
                <DialogDescription>
                  Enter a new name for this {renameItem?.type}
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="rename-input">New Name</Label>
                  <Input
                    id="rename-input"
                    value={newItemName}
                    onChange={(e) => setNewItemName(e.target.value)}
                    placeholder={`Enter new ${renameItem?.type} name`}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => {
                  setIsRenameDialogOpen(false)
                  setRenameItem(null)
                  setNewItemName('')
                }}>
                  Cancel
                </Button>
                <Button onClick={handleRename} disabled={!newItemName.trim()}>
                  Rename
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* File Explorer Interface */}
      <div className="grid gap-6 lg:grid-cols-5 h-[calc(100vh-12rem)]">
        {/* Folder Tree Sidebar */}
        <div className="lg:col-span-1">
          <Card className="h-full">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Folders</CardTitle>
              <CardDescription className="text-xs">
                Right-click for options
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0" onClick={(e) => {
              // Clear active folder when clicking outside folders
              if (e.target === e.currentTarget) {
                setActiveFolder('')
              }
            }}>
              <div className="space-y-1 max-h-[400px] overflow-y-auto">
                {loading ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                      <span className="text-xs text-muted-foreground">Loading folders...</span>
                    </div>
                  </div>
                ) : folders.length === 0 ? (
                  <div className="p-4 text-sm text-muted-foreground text-center">
                    No folders yet
                  </div>
                ) : (
                  folders.map((folder, index) => {
                    return renderFolderTree(folder)
                  })
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Area */}
        <div className="lg:col-span-4">
          <Card className="h-full">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">Documents</CardTitle>
                  <CardDescription className="text-xs">
                    {documents.length} items • Right-click for options
                  </CardDescription>
                  {activeFolder && (
                    <div className="mt-2 text-sm text-muted-foreground">
                      <span className="font-medium">Current path:</span> {
                        (() => {
                          // Function to find folder in entire tree (including children)
                          const findFolderInTree = (tree: any[], targetId: string): any => {
                            for (const folder of tree) {
                              if (folder.id === targetId) {
                                return folder
                              }
                              if (folder.children && folder.children.length > 0) {
                                const found = findFolderInTree(folder.children, targetId)
                                if (found) return found
                              }
                            }
                            return null
                          }

                          const activeFolderObj = findFolderInTree(folders, activeFolder)

                          // Function to build full path from folder hierarchy
                          const buildFullPath = (folderObj: any): string => {
                            if (!folderObj) return activeFolder

                            // For access level folders, build path from parent
                            if (folderObj.type === 'access_level') {
                              // First try: search through all departments' children (most reliable)
                              for (const dept of folders) {
                                if (dept.type === 'department' && dept.children) {
                                  const foundChild = dept.children.find((child: any) => child.id === folderObj.id)
                                  if (foundChild) {
                                    return `${dept.name}/${folderObj.name}`
                                  }
                                }
                              }

                              // Second try: use parent_folder_id if available
                              if (folderObj.parent_folder_id) {
                                const parentDept = folders.find(f => f.id === folderObj.parent_folder_id)
                                if (parentDept) {
                                  return `${parentDept.name}/${folderObj.name}`
                                }
                              }

                              // Third try: use department_name property
                              if (folderObj.department_name) {
                                return `${folderObj.department_name}/${folderObj.name}`
                              }

                              // Fourth try: extract from path
                              if (folderObj.path && folderObj.path.includes('/')) {
                                return folderObj.path
                              }
                            }

                            // For department folders
                            if (folderObj.type === 'department') {
                              return folderObj.name
                            }

                            // For regular folders, use path if available
                            if (folderObj.path) {
                              return folderObj.path
                            }

                            return folderObj.name || activeFolder
                          }

                          return buildFullPath(activeFolderObj)
                        })()
                      }
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="h-8">
                    <FileText className="h-3 w-3 mr-1" />
                    List
                  </Button>
                  <Button variant="outline" size="sm" className="h-8">
                    <Folder className="h-3 w-3 mr-1" />
                    Grid
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div
                className="min-h-[400px] border-2 border-dashed border-border/50 rounded-lg m-4"
                onContextMenu={(e) => handleContextMenu(e, 'background')}
                onClick={closeContextMenu}
                onDrop={(e) => {
                  e.preventDefault()
                  const files = Array.from(e.dataTransfer.files)
                  if (files.length > 0) {
                    setSelectedFiles(files)
                    setIsBatchUpload(true)
                    setIsUploadDialogOpen(true)
                  }
                }}
                onDragOver={(e) => e.preventDefault()}
              >
                {loading ? (
                  <div className="flex items-center justify-center h-full py-12">
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                      <span className="text-xs text-muted-foreground">Loading documents...</span>
                    </div>
                  </div>
                ) : documents.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full py-12">
                    <FileText className="h-16 w-16 text-muted-foreground/50 mb-4" />
                    <h3 className="text-lg font-medium text-muted-foreground mb-2">No documents yet</h3>
                    <p className="text-sm text-muted-foreground text-center max-w-sm">
                      Upload your first document by dragging files here or using the upload button above
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-2 p-4 grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="group flex flex-col items-center p-3 rounded-lg hover:bg-accent cursor-pointer border border-transparent hover:border-border transition-all"
            title={doc.path_display || doc.filename}
            onContextMenu={(e) => handleContextMenu(e, 'document', doc)}
            onClick={closeContextMenu}
            onDoubleClick={() => {
              const downloadUrl = `/api/v1/documents/download/${doc.id}`
              const link = document.createElement('a')
              link.href = downloadUrl
              link.download = doc.name || `document_${doc.id}`
              document.body.appendChild(link)
              link.click()
              document.body.removeChild(link)

              toast({
                title: 'Download started',
                description: `Downloading ${doc.filename}`,
              })
            }}
          >
            {/* File Icon */}
            <div className="text-3xl mb-2">{getFileIcon(doc.filename)}</div>

            {/* File Name */}
            <div className="text-center">
              <p className="text-sm font-medium truncate w-full max-w-[120px]" title={doc.filename}>
                {doc.filename}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {formatFileSize(doc.file_size)}
              </p>
            </div>

            {/* Action Buttons - Show on hover */}
            <div className="flex gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={(e) => {
                  e.stopPropagation()
                  const downloadUrl = `/api/v1/documents/download/${doc.id}`
                  const link = document.createElement('a')
                  link.href = downloadUrl
                  link.download = doc.name || `document_${doc.id}`
                  document.body.appendChild(link)
                  link.click()
                  document.body.removeChild(link)

                  toast({
                    title: 'Download started',
                    description: `Downloading ${doc.filename}`,
                  })
                }}
              >
                <Download className="h-3 w-3" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(doc.id)
                }}
                disabled={deleting === doc.id}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </div>
        ))}

                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Upload Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>Supported File Types</CardTitle>
          <CardDescription>
            Files that can be uploaded to your organization
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <h4 className="font-medium mb-2">Documents</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• PDF (.pdf)</li>
                <li>• Word (.doc, .docx)</li>
                <li>• Text (.txt)</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium mb-2">Other Files</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Excel (.xls, .xlsx)</li>
                <li>• PowerPoint (.ppt, .pptx)</li>
                <li>• Images (.jpg, .jpeg, .png, .gif)</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Enhanced Context Menu */}
      {contextMenu && (
        <div
          className="fixed z-50 bg-popover border border-border rounded-md shadow-lg p-1 min-w-[200px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {contextMenu.type === 'background' && (
            <>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2"
                onClick={() => handleContextMenuAction('newFolder')}
              >
                <Plus className="w-4 h-4" />
                New Folder
              </button>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2"
                onClick={() => handleContextMenuAction('uploadDocument')}
              >
                <Upload className="w-4 h-4" />
                Upload Files
              </button>
              <div className="border-t border-border my-1"></div>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2"
                onClick={() => handleContextMenuAction('refresh')}
              >
                <FileText className="w-4 h-4" />
                Refresh
              </button>
            </>
          )}
          {contextMenu.type === 'document' && (
            <>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2"
                onClick={() => handleContextMenuAction('open')}
              >
                <FileText className="w-4 h-4" />
                Open
              </button>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2"
                onClick={() => handleContextMenuAction('download')}
              >
                <Download className="w-4 h-4" />
                Download
              </button>
              <div className="border-t border-border my-1"></div>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2 text-destructive"
                onClick={() => handleContextMenuAction('delete')}
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </>
          )}
          {contextMenu.type === 'folder' && (
            <>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2"
                onClick={() => handleContextMenuAction('open')}
              >
                <Folder className="w-4 h-4" />
                Open
              </button>
              <button
                className={`w-full text-left px-3 py-2 text-sm rounded-sm flex items-center gap-2 ${
                  !activeFolder ? 'opacity-50 cursor-not-allowed text-muted-foreground' : 'hover:bg-accent'
                }`}
                onClick={() => handleContextMenuAction('newFolder')}
                disabled={!activeFolder}
                title={!activeFolder ? 'Select a folder first to create subfolder' : ''}
              >
                <Plus className="w-4 h-4" />
                New Folder
              </button>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2"
                onClick={() => handleContextMenuAction('uploadDocument')}
              >
                <Upload className="w-4 h-4" />
                Upload Here
              </button>
              <div className="border-t border-border my-1"></div>
              <button
                className={`w-full text-left px-3 py-2 text-sm rounded-sm flex items-center gap-2 ${
                  (contextMenu.item?.name === 'Public' || contextMenu.item?.folder_name === 'Public' ||
                   contextMenu.item?.name === 'Private' || contextMenu.item?.folder_name === 'Private')
                    ? 'opacity-50 cursor-not-allowed text-muted-foreground'
                    : 'hover:bg-accent'
                }`}
                onClick={() => handleContextMenuAction('rename')}
                disabled={contextMenu.item?.name === 'Public' || contextMenu.item?.folder_name === 'Public' ||
                         contextMenu.item?.name === 'Private' || contextMenu.item?.folder_name === 'Private'}
              >
                <FileText className="w-4 h-4" />
                Rename
              </button>
              <button
                className={`w-full text-left px-3 py-2 text-sm rounded-sm flex items-center gap-2 ${
                  (contextMenu.item?.name === 'Public' || contextMenu.item?.folder_name === 'Public' ||
                   contextMenu.item?.name === 'Private' || contextMenu.item?.folder_name === 'Private')
                    ? 'opacity-50 cursor-not-allowed text-muted-foreground'
                    : 'hover:bg-accent text-destructive'
                }`}
                onClick={() => handleContextMenuAction('delete')}
                disabled={contextMenu.item?.name === 'Public' || contextMenu.item?.folder_name === 'Public' ||
                         contextMenu.item?.name === 'Private' || contextMenu.item?.folder_name === 'Private'}
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
