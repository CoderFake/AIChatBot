'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FileText, Upload, Download, Trash2, Plus, File, Folder, MoreVertical } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from 'react-i18next'
import { apiService } from '@/lib/api/index'
import type { Department } from '@/types'

interface Document {
  id: string
  filename: string
  name: string
  file_path: string
  file_size: number
  content_type: string
  uploaded_by: string
  department_id?: string
  created_at: string
}

interface DocumentManagementProps {
  tenantId: string
}

export function DocumentManagement({ tenantId }: DocumentManagementProps) {
  const { toast } = useToast()
  const { t } = useTranslation()
  const [documents, setDocuments] = useState<Document[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedDepartment, setSelectedDepartment] = useState<string>('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const [folders, setFolders] = useState<any[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string>('')
  const [isFolderDialogOpen, setIsFolderDialogOpen] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [parentFolder, setParentFolder] = useState<string>('')
  const [selectedAccessLevel, setSelectedAccessLevel] = useState<'private' | 'public'>('private')
  const [contextMenu, setContextMenu] = useState<{
    x: number
    y: number
    type: 'folder' | 'document' | 'background'
    item?: any
  } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    loadData()
  }, [tenantId])

  const loadFolders = async () => {
    try {
      const [publicTree, privateTree] = await Promise.all([
        apiService.documents.getTree('public'),
        apiService.documents.getTree('private')
      ])

      const flat: any[] = []

      // Add public folders
      if (publicTree?.folders || publicTree) {
        const traversePublic = (nodes: any[], depth = 0, path = '') => {
          nodes.forEach((n) => {
            const currentPath = path ? `${path}/${n.name}` : n.name
            flat.push({
              id: n.id,
              name: `${'—'.repeat(depth)}${n.name}`,
              access_level: 'public',
              path: currentPath
            })
            if (n.children) traversePublic(n.children, depth + 1, currentPath)
          })
        }
        traversePublic(publicTree.folders || publicTree || [], 0, 'public')
      }

      // Add private folders
      if (privateTree?.folders || privateTree) {
        const traversePrivate = (nodes: any[], depth = 0, path = '') => {
          nodes.forEach((n) => {
            const currentPath = path ? `${path}/${n.name}` : n.name
            flat.push({
              id: n.id,
              name: `${'—'.repeat(depth)}${n.name}`,
              access_level: 'private',
              path: currentPath
            })
            if (n.children) traversePrivate(n.children, depth + 1, currentPath)
          })
        }
        traversePrivate(privateTree.folders || privateTree || [], 0, 'private')
      }

      setFolders(flat)
    } catch (error) {
      console.error('Failed to load folders:', error)
      toast({
        title: 'Error',
        description: 'Failed to load folders',
        variant: 'destructive',
      })
    }
  }

  const loadData = async () => {
    try {
      setLoading(true)
      const [docResponse, deptResponse] = await Promise.all([
        apiService.documents.list(tenantId),
        apiService.departments.list(tenantId)
      ])

      setDocuments(docResponse.documents || [])
      setDepartments(deptResponse || [])
      await loadFolders()
    } catch (error) {
      console.error('Failed to load data:', error)
      toast({
        title: "Error",
        description: "Failed to load documents and departments",
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

  const handleUpload = async () => {
    if (!selectedFile) return

    try {
      setUploading(true)
      await apiService.documents.upload(selectedFile, {
        collection_name: selectedDepartment || 'default',
        access_level: selectedAccessLevel,
        folder_id: selectedFolder || undefined,
      })

      toast({
        title: "Success",
        description: "Document uploaded successfully",
      })

      setIsUploadDialogOpen(false)
      setSelectedFile(null)
      setSelectedDepartment('')
      setSelectedFolder('')
      setSelectedAccessLevel('private')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      loadData()
    } catch (error) {
      console.error('Failed to upload document:', error)
      toast({
        title: "Error",
        description: "Failed to upload document",
        variant: "destructive",
      })
    } finally {
      setUploading(false)
    }
  }

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return
    try {
      await apiService.documents.createFolder(newFolderName.trim(), parentFolder || undefined)
      toast({ title: 'Success', description: 'Folder created successfully' })
      setIsFolderDialogOpen(false)
      setNewFolderName('')
      setParentFolder('')
      await loadFolders()
    } catch (error) {
      console.error('Failed to create folder:', error)
      toast({ title: 'Error', description: 'Failed to create folder', variant: 'destructive' })
    }
  }

  const handleDelete = async (documentId: string) => {
    try {
      setDeleting(documentId)
      await apiService.documents.delete(documentId)

      toast({
        title: "Success",
        description: "Document deleted successfully",
      })

      loadData()
    } catch (error) {
      console.error('Failed to delete document:', error)
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

  const handleContextMenuAction = (action: string) => {
    if (!contextMenu) return

    switch (action) {
      case 'newFolder':
        setIsFolderDialogOpen(true)
        break
      case 'uploadDocument':
        setIsUploadDialogOpen(true)
        break
      case 'delete':
        if (contextMenu.type === 'document' && contextMenu.item) {
          handleDelete(contextMenu.item.id)
        }
        break
    }

    setContextMenu(null)
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
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
              <Button className="gap-2">
                <Upload className="h-4 w-4" />
                Upload Document
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Upload Document</DialogTitle>
                <DialogDescription>
                  Upload a document to your organization
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="file-upload">File</Label>
                  <Input
                    id="file-upload"
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    accept=".pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif"
                  />
                  {selectedFile && (
                    <p className="text-sm text-muted-foreground">
                      Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                    </p>
                  )}
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="folder-select">Folder</Label>
                  <Select value={selectedFolder} onValueChange={setSelectedFolder}>
                    <SelectTrigger id="folder-select">
                      <SelectValue placeholder="Select folder" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">Root</SelectItem>
                      {folders.map((f) => (
                        <SelectItem key={f.id} value={f.id}>
                          {f.access_level === 'public' ? '🌐 ' : '🔒 '}{f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="department-select">Department (Optional)</Label>
                  <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select department" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">No department</SelectItem>
                      {departments.map((dept) => (
                        <SelectItem key={dept.id} value={dept.id}>
                          {dept.department_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="access-level-select">Access Level</Label>
                  <Select value={selectedAccessLevel} onValueChange={(value) => setSelectedAccessLevel(value as 'private' | 'public')}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select access level" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="private">🔒 Private</SelectItem>
                      <SelectItem value="public">🌐 Public</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsUploadDialogOpen(false)
                    setSelectedFile(null)
                    setSelectedDepartment('')
                    setSelectedFolder('')
                    setSelectedAccessLevel('private')
                    if (fileInputRef.current) {
                      fileInputRef.current.value = ''
                    }
                  }}
                  disabled={uploading}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleUpload}
                  disabled={!selectedFile || uploading}
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={isFolderDialogOpen} onOpenChange={setIsFolderDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2">
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
                <div className="grid gap-2">
                  <Label htmlFor="parent-folder">Parent Folder (Optional)</Label>
                  <Select value={parentFolder} onValueChange={setParentFolder}>
                    <SelectTrigger id="parent-folder">
                      <SelectValue placeholder="Select parent" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">Root</SelectItem>
                      {folders.map((f) => (
                        <SelectItem key={f.id} value={f.id}>
                          {f.access_level === 'public' ? '🌐 ' : '🔒 '}{f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsFolderDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreateFolder} disabled={!newFolderName.trim()}>
                  Create
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Documents Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {documents.map((doc) => (
          <Card
            key={doc.id}
            className="hover:shadow-md transition-shadow"
            onContextMenu={(e) => handleContextMenu(e, 'document', doc)}
            onClick={closeContextMenu}
          >
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="text-2xl">{getFileIcon(doc.filename)}</div>
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-lg truncate" title={doc.filename}>
                    {doc.filename}
                  </CardTitle>
                  <CardDescription>
                    {formatFileSize(doc.file_size)} • {new Date(doc.created_at).toLocaleDateString()}
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  <p>Uploaded by: {doc.uploaded_by}</p>
                  {doc.department_id && (
                    <p>Department: {departments.find(d => d.id === doc.department_id)?.department_name || 'Unknown'}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const downloadUrl = `/api/v1/documents/download/${doc.id}`
                      const link = document.createElement('a')
                      link.href = downloadUrl
                      link.download = doc.name || `document_${doc.id}`
                      document.body.appendChild(link)
                      link.click()
                      document.body.removeChild(link)

                      toast({
                        title: t('notifications.success'),
                        description: t('documents.downloadStarted'),
                      })
                    }}
                    className="h-8 w-8 p-0"
                  >
                    <Download className="h-4 w-4" />
                  </Button>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                        disabled={deleting === doc.id}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete Document</AlertDialogTitle>
                        <AlertDialogDescription>
                          Are you sure you want to delete "{doc.filename}"?
                          This action cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => handleDelete(doc.id)}
                          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                          Delete
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {documents.length === 0 && (
          <div className="col-span-full text-center py-12">
            <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No documents yet</h3>
            <p className="text-muted-foreground">
              Upload your first document to get started
            </p>
          </div>
        )}
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

      {/* Context Menu */}
      {contextMenu && (
        <div
          className="fixed z-50 bg-popover border border-border rounded-md shadow-md p-1"
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
                Upload Document
              </button>
            </>
          )}
          {contextMenu.type === 'document' && (
            <button
              className="w-full text-left px-3 py-2 text-sm hover:bg-accent rounded-sm flex items-center gap-2 text-destructive"
              onClick={() => handleContextMenuAction('delete')}
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          )}
        </div>
      )}
    </div>
  )
}
