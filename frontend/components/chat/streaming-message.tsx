"use client"

import { useState, useEffect, useRef } from "react"
import { ChevronRight, ChevronDown, CheckCircle, Clock, AlertCircle, ChevronLeft } from "lucide-react"
import { MarkdownMessage } from "./markdown-message"

interface ThinkingIndicatorProps {
  className?: string
  planningData?: PlanningData
  executionData?: ExecutionData
  progress?: number
}

export function ThinkingIndicator({ className = "", planningData, executionData, progress }: ThinkingIndicatorProps) {
  const [currentDot, setCurrentDot] = useState(0)
  const [showDropdown, setShowDropdown] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentDot((prev) => (prev + 1) % 3)
    }, 500)

    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showDropdown && !(event.target as Element).closest('.thinking-dropdown')) {
        setShowDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showDropdown])

  return (
    <div className={`thinking-dropdown relative flex items-center gap-2 max-w-full ${className}`}>
      {/* Thinking text with cursor-like underline effect */}
      <div className="relative flex items-center">
        <span className="shimmer-text font-semibold text-base tracking-wide select-none">
          thinking
        </span>

        {/* Animated dots (smaller and subtle) */}
        <div className="flex gap-1 ml-2">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-blue-500 transition-all duration-500 ease-in-out"
              style={{
                transform: `scale(${currentDot === i ? 1.2 : 0.85})`,
                opacity: currentDot === i ? 0.9 : 0.5,
                ...(currentDot === i ? {
                  animation: `bounce 0.8s ease-in-out infinite`,
                  animationDelay: `${i * 0.15}s`
                } : {
                  animation: 'none'
                })
              }}
            />
          ))}
        </div>
      </div>

      {/* Expand arrow button to reveal plan list/details */}
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="ml-1 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors opacity-70 hover:opacity-100"
        title="View execution details"
      >
        <ChevronRight
          size={12}
          className={`text-gray-500 transition-transform duration-200 ${showDropdown ? 'rotate-90' : ''}`}
        />
      </button>

      {/* Dropdown with plan/progress, compact typography */}
      {showDropdown && (
        <div
          className="absolute top-full left-0 mt-2 w-full max-w-xs sm:max-w-sm md:max-w-md bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-10 overflow-hidden"
          style={{
            animation: 'dropdown-fade-in 0.2s ease-out',
            maxWidth: 'min(20rem, calc(100% - 0.5rem))'
          }}
        >
          <div className="p-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-medium text-xs text-gray-900 dark:text-gray-100">Execution Details</h4>
              <button
                onClick={() => setShowDropdown(false)}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                <ChevronLeft size={12} className="text-gray-500" />
              </button>
            </div>

            {/* Progress bar */}
            {progress !== undefined && (
              <div className="mb-2">
                <div className="flex justify-between text-[10px] text-gray-600 dark:text-gray-400 mb-1">
                  <span>Progress</span>
                  <span>{progress}%</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                  <div
                    className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Task status list */}
            {planningData?.formatted_tasks && planningData.formatted_tasks.length > 0 && (
              <div className="mb-3">
                <div className="flex items-center gap-2 text-[11px] font-medium text-gray-800 dark:text-gray-100 mb-1">
                  <ChevronRight size={12} className="text-blue-500" />
                  <span>Task execution timeline</span>
                </div>
                <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  {(() => {
                    const allTasksCompleted = planningData.formatted_tasks.every((task: any) => (task.status || 'pending') === 'completed')

                    return planningData.formatted_tasks.map((task: any, index: number) => {
                      const status = task.status || 'pending'
                      const isCompleted = status === 'completed'
                      const isFailed = status === 'failed'
                      const isRunning = status === 'in_progress'
                      const statusText = isCompleted ? 'Completed' : isFailed ? 'Failed' : isRunning ? 'Running' : status === 'retrying' ? 'Retrying' : 'Pending'

                      const severity = task.severity || task.color || (isCompleted ? 'success' : isFailed ? 'danger' : isRunning || status === 'retrying' ? 'info' : 'pending')

                      const baseClasses = (() => {
                        const colorToUse = task.color || severity
                        
                        if (colorToUse === 'success') {
                          // Enhanced green for successful retries
                          const isRetrySuccess = task.retry_attempts > 0 || task.retry_count > 0
                          return allTasksCompleted && isCompleted
                            ? 'bg-green-100 dark:bg-green-900 border-green-300 dark:border-green-600 text-green-800 dark:text-green-200'
                            : isRetrySuccess && isCompleted
                            ? 'bg-green-100 dark:bg-green-900 border-green-300 dark:border-green-600 text-green-800 dark:text-green-200' // Special styling for retry success
                            : 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300'
                        }

                        if (colorToUse === 'danger') {
                          return 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
                        }

                        if (colorToUse === 'primary' || colorToUse === 'info') {
                          return 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300'
                        }

                        return 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300'
                      })()

                      const retryHistory = Array.isArray(task.retry_history) ? task.retry_history : []
                      const retryAttempts = typeof task.retry_attempts === 'number' ? task.retry_attempts : (typeof task.retry_count === 'number' ? task.retry_count : retryHistory.length) || 0
                      const maxRetries = typeof task.max_retries === 'number' ? task.max_retries : 0

                      return (
                        <div
                          key={task.task_index ?? index}
                          className={`flex items-start gap-2 border rounded-md px-2 py-2 text-[11px] ${baseClasses}`}
                        >
                          {isCompleted ? (
                            <CheckCircle size={12} className={`mt-0.5 ${
                              (task.retry_attempts > 0 || task.retry_count > 0) 
                                ? 'text-green-600'
                                : allTasksCompleted 
                                ? 'text-green-600' 
                                : 'text-green-500'
                            }`} />
                          ) : isFailed ? (
                            <AlertCircle size={12} className="mt-0.5 text-red-500" />
                          ) : (
                            <div className={`mt-0.5 w-2 h-2 rounded-full bg-blue-500 ${isRunning ? 'animate-pulse' : ''}`} />
                          )}
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold truncate">{task.task_name || `Task ${index + 1}`}</div>
                          <div className="text-[10px] opacity-80 truncate">
                            {task.agent ? `${task.agent}` : 'Agent'}
                            {task.messages && Object.keys(task.messages).length > 0 && (
                              <span className="ml-1">
                                — {Object.values(task.messages).join(' › ')}
                              </span>
                            )}
                          </div>
                          {task.error && (
                            <div className="text-[10px] mt-1 text-red-500 dark:text-red-300 truncate">
                              {task.error}
                            </div>
                          )}
                          {retryHistory.length > 0 && (
                            <div className="mt-1 space-y-1">
                              <div className="text-[9px] uppercase tracking-wide font-semibold text-gray-500 dark:text-gray-400">
                                Retry attempts ({Math.min(retryAttempts + 1, maxRetries || retryAttempts + 1)}/{maxRetries || retryAttempts + 1})
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {retryHistory.map((attempt: any, attemptIndex: number) => {
                                  const attemptStatus = attempt?.status === 'completed' ? 'completed' : 'failed'
                                  const chipClasses = attemptStatus === 'completed'
                                    ? 'bg-green-100 text-green-700 dark:bg-green-900/60 dark:text-green-200 border border-green-200 dark:border-green-800'
                                    : 'bg-red-100 text-red-700 dark:bg-red-900/60 dark:text-red-200 border border-red-200 dark:border-red-800'

                                  const errorSnippet = typeof attempt?.error === 'string'
                                    ? `${attempt.error.slice(0, 80)}${attempt.error.length > 80 ? '…' : ''}`
                                    : ''

                                  const toolLabel = attempt?.tool ? `${attempt.tool}` : 'Tool'

                                  return (
                                    <span
                                      key={`${toolLabel}-${attempt?.attempt ?? attemptIndex}-${attemptStatus}`}
                                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-medium ${chipClasses}`}
                                    >
                                      <span>#{attempt?.attempt ?? attemptIndex + 1}</span>
                                      <span className="truncate">
                                        {toolLabel}: {attemptStatus === 'completed' ? 'Success' : 'Failed'}
                                        {errorSnippet ? ` — ${errorSnippet}` : ''}
                                      </span>
                                    </span>
                                  )
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                        <span className="text-[10px] font-medium whitespace-nowrap">{statusText}</span>
                      </div>
                    )})
                  })()}
                </div>
              </div>
            )}

            {/* Planning Section (compact) */}
            {planningData && (
              <div className="mb-2">
                <div className="flex items-center gap-2 text-[11px] font-medium text-blue-600 dark:text-blue-400 mb-1">
                  <Clock size={12} />
                  <span>Planning</span>
                </div>
                {planningData.execution_plan && (
                  <div className="text-[11px] text-gray-600 dark:text-gray-400 bg-blue-50 dark:bg-blue-950 p-2 rounded">
                    <div>Tasks: {planningData.execution_plan.execution_flow?.planning?.tasks?.length || 0}</div>
                    <div>Total Steps: {planningData.execution_plan.total_steps || 0}</div>
                  </div>
                )}
              </div>
            )}

            {/* Plan list details when available */}
            {planningData?.execution_plan?.steps?.length > 0 && (
              <div className="space-y-1 max-h-56 overflow-auto pr-1">
                {(planningData?.execution_plan?.steps ?? []).map((step: any, index: number) => (
                  <div
                    key={index}
                    className={`flex items-start gap-2 p-2 rounded text-[11px] border ${
                      step.status === 'completed'
                        ? 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800'
                        : step.status === 'running'
                        ? 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800'
                        : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    {step.status === 'completed' ? (
                      <CheckCircle size={10} className="text-green-600 flex-shrink-0 mt-0.5" />
                    ) : step.status === 'running' ? (
                      <div className="w-2.5 h-2.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0 mt-0.5"></div>
                    ) : (
                      <div className="w-2.5 h-2.5 border-2 border-gray-300 rounded-full flex-shrink-0 mt-0.5"></div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">Step {index + 1}: {step.step_id || `Step ${index + 1}`}</div>
                      {step.tasks?.length > 0 && (
                        <div className="text-gray-600 dark:text-gray-400 mt-0.5 truncate">
                          {step.tasks.length} task{step.tasks.length > 1 ? 's' : ''}: {step.tasks.map((task: any) => `${task.agent || 'Agent'} (${task.tool || 'Tool'})`).join(', ')}
                        </div>
                      )}
                    </div>
                    <div className={`text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap ${
                      step.status === 'completed'
                        ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300'
                        : step.status === 'running'
                        ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                        : 'bg-gray-100 dark:bg-gray-900 text-gray-700 dark:text-gray-300'
                    }`}>
                      {step.status || 'pending'}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Execution Section (compact) */}
            {executionData && (
              <div className="mt-2">
                <div className="flex items-center gap-2 text-[11px] font-medium text-green-600 dark:text-green-400 mb-1">
                  <CheckCircle size={12} />
                  <span>Execution</span>
                </div>
                <div className="space-y-1">
                  {executionData.agent_responses?.map((response, index) => (
                    <div key={index} className="flex items-center gap-2 text-[11px] bg-green-50 dark:bg-green-950 p-2 rounded">
                      <CheckCircle size={10} className="text-green-600" />
                      <span className="font-medium truncate">{response.agent || 'Agent'}</span>
                      <span className="text-gray-600 dark:text-gray-400 truncate">
                        {response.tool || 'Tool'} - {response.status || 'Completed'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!planningData && !executionData && (
              <div className="text-[11px] text-gray-500 dark:text-gray-400 text-center py-3">
                No execution details available yet
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

interface PlanningData {
  semantic_routing?: any
  execution_plan?: any
  formatted_tasks?: any[]
  progress?: number
  status?: string
  message?: string
  task_status_update?: {
    type: string
    task_index?: number
    status?: string
    color?: 'primary' | 'success' | 'danger' | 'info'
    all_tasks_status?: string
  }
}

interface ExecutionData {
  current_step_results?: any[]
  agent_responses?: any[]
  execution_plan?: any
}

interface StreamingMessageProps {
  content: string
  isStreaming: boolean
  planningData?: PlanningData
  executionData?: ExecutionData
  progress?: number
  status?: string
  onDocumentClick?: (documentId: string, url: string, title?: string) => void
}

export function StreamingMessage({
  content,
  isStreaming,
  planningData,
  executionData,
  progress,
  status,
  onDocumentClick
}: StreamingMessageProps) {
  const [displayedContent, setDisplayedContent] = useState("")
  const [isPlanningExpanded, setIsPlanningExpanded] = useState(false)
  const [isExecutionExpanded, setIsExecutionExpanded] = useState(true) // Auto expand execution
  const messageRef = useRef<HTMLDivElement>(null)

  const renderTaskContext = (purpose: any) => {
    if (!purpose) return null

    if (typeof purpose === 'object' && purpose.context) {
      return (
        <div className="space-y-1 text-xs">
          {purpose.context && (
            <div className="break-words">
              <span className="font-medium text-gray-700 dark:text-gray-300">Context:</span>{' '}
              <span className="text-gray-600 dark:text-gray-400">{purpose.context}</span>
            </div>
          )}
          {purpose.task && (
            <div className="break-words">
              <span className="font-medium text-gray-700 dark:text-gray-300">Task:</span>{' '}
              <span className="text-gray-600 dark:text-gray-400">{purpose.task}</span>
            </div>
          )}
        </div>
      )
    }

    // Fallback for string format
    if (typeof purpose === 'string') {
      return (
        <div className="text-xs text-gray-600 dark:text-gray-400 break-words">
          {purpose.split('\n').map((line, idx) => (
            <div key={idx} className={idx > 0 ? 'mt-1' : ''}>
              {line.trim()}
            </div>
          ))}
        </div>
      )
    }

    return null
  }

  useEffect(() => {
    if (isStreaming) {
      setDisplayedContent(content)
    } else {
      setDisplayedContent(content)
    }
  }, [content, isStreaming])

  // Blinking cursor effect - DISABLED
  // useEffect(() => {
  //   if (!isStreaming) {
  //     setShowCursor(false)
  //     return
  //   }

  //   const interval = setInterval(() => {
  //     setShowCursor((prev) => !prev)
  //   }, 500)

  //   return () => clearInterval(interval)
  // }, [isStreaming])

  // Auto-scroll to keep message in view
  useEffect(() => {
    if (messageRef.current) {
      messageRef.current.scrollIntoView({ behavior: "smooth", block: "end" })
    }
  }, [displayedContent])

  const renderPlanningSection = () => {
    if (!planningData) return null

    return (
      <div className="border border-blue-200 rounded-md p-2 mb-3 bg-blue-50 dark:bg-blue-950 w-full overflow-hidden break-words">
        <button
          onClick={() => setIsPlanningExpanded(!isPlanningExpanded)}
          className="flex items-center gap-2 text-blue-700 dark:text-blue-300 text-sm font-medium hover:text-blue-800 dark:hover:text-blue-200 transition-colors"
        >
          {isPlanningExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className="text-sm">Planning & Analysis</span>
          <span className="text-xs bg-blue-200 dark:bg-blue-800 px-1.5 py-0.5 rounded flex items-center gap-1">
            {progress === 100 ? (
              <>
                <CheckCircle size={8} className="text-green-600" />
                <span className="text-xs">Completed</span>
              </>
            ) : (
              `${progress || 0}%`
            )}
          </span>
        </button>

        {isPlanningExpanded && (
          <div className="mt-3 space-y-3 max-w-full">
            {planningData.formatted_tasks && planningData.formatted_tasks.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded p-3 border overflow-hidden max-w-full">
                <h4 className="font-medium text-sm mb-2">Task Progress</h4>
                <div className="space-y-2">
                  {(() => {
                    // Check if all tasks are completed
                    const allTasksCompleted = planningData.formatted_tasks.every((task: any) => (task.status || 'pending') === 'completed')

                    return planningData.formatted_tasks.map((task: any, index: number) => {
                      const status = task.status || 'pending'
                      const isCompleted = status === 'completed'
                      const isFailed = status === 'failed'
                      const isRunning = status === 'in_progress'
                      const statusText = isCompleted ? 'Completed' : isFailed ? 'Failed' : isRunning ? 'Running' : 'Pending'

                      const colorToUse = task.color || (isCompleted ? 'success' : isFailed ? 'danger' : isRunning ? 'primary' : 'pending')
                      
                      const taskClasses = (() => {
                        if (colorToUse === 'success') {
                          const isRetrySuccess = task.retry_attempts > 0 || task.retry_count > 0
                          return allTasksCompleted && isCompleted
                            ? 'bg-green-100 dark:bg-green-900 border-green-300 dark:border-green-600 text-green-800 dark:text-green-200'
                            : isRetrySuccess && isCompleted
                            ? 'bg-green-100 dark:bg-green-900 border-green-300 dark:border-green-600 text-green-800 dark:text-green-200' // Special styling for retry success
                            : 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300'
                        }
                        if (colorToUse === 'danger') {
                          return 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
                        }
                        if (colorToUse === 'primary') {
                          return 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300'
                        }
                        return 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300'
                      })()

                      return (
                        <div
                          key={task.task_index ?? index}
                          className={`flex items-start gap-3 p-2 rounded text-xs border ${taskClasses}`}
                        >
                        {isCompleted ? (
                          <CheckCircle size={12} className={`mt-0.5 ${
                            (task.retry_attempts > 0 || task.retry_count > 0) 
                              ? 'text-green-600' // Bright green for successful retries
                              : allTasksCompleted 
                              ? 'text-green-600' 
                              : 'text-green-500'
                          }`} />
                        ) : isFailed ? (
                          <AlertCircle size={12} className="mt-0.5 text-red-500" />
                        ) : (
                          <div className={`mt-0.5 w-2 h-2 rounded-full bg-blue-500 ${isRunning ? 'animate-pulse' : ''}`} />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold truncate">{task.task_name || `Task ${index + 1}`}</div>
                          <div className="text-gray-600 dark:text-gray-400 mt-0.5 truncate">
                            {task.agent || 'Agent'}
                            {task.messages && Object.keys(task.messages).length > 0 && (
                              <span className="ml-1">— {Object.values(task.messages).join(' › ')}</span>
                            )}
                          </div>
                          {task.error && (
                            <div className="text-red-500 dark:text-red-300 text-[11px] mt-1 truncate">{task.error}</div>
                          )}
                        </div>
                        <span className="text-[11px] font-medium whitespace-nowrap">{statusText}</span>
                      </div>
                      )
                    })
                  })()}
                </div>
              </div>
            )}

            {/* Task Details Section */}
            {planningData.execution_plan?.steps?.some((step: any) =>
              step.tasks?.some((task: any) => task.purpose)
            ) && (
              <div className="bg-white dark:bg-gray-800 rounded p-3 border overflow-hidden max-w-full">
                <h4 className="font-medium text-sm mb-2">Task Details</h4>
                <div className="space-y-3">
                  {planningData.execution_plan.steps.map((step: any, stepIndex: number) =>
                    step.tasks?.map((task: any, taskIndex: number) => (
                      task.purpose && (
                        <div key={`${stepIndex}-${taskIndex}`} className="border-l-2 border-blue-300 pl-3">
                          <div className="font-medium text-xs text-gray-700 dark:text-gray-300 mb-1">
                            {task.agent || 'Agent'}: {task.tool || 'Tool'}
                          </div>
                          {renderTaskContext(task.purpose)}
                        </div>
                      )
                    ))
                  )}
                </div>
              </div>
            )}

            {planningData.execution_plan && (
              <div className="bg-white dark:bg-gray-800 rounded p-3 border overflow-hidden max-w-full">
                <h4 className="font-medium text-sm mb-2">Execution Plan Steps</h4>
                <div className="space-y-2">
                  {planningData.execution_plan.steps && planningData.execution_plan.steps.length > 0 ? (
                    planningData.execution_plan.steps.map((step: any, index: number) => (
                      <div
                        key={index}
                        className={`flex items-center gap-2 p-2 rounded text-xs border overflow-hidden break-words ${
                          step.status === 'completed'
                            ? 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800'
                            : step.status === 'running'
                            ? 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800'
                            : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700'
                        }`}
                      >
                        {step.status === 'completed' ? (
                          <CheckCircle size={12} className="text-green-600 flex-shrink-0" />
                        ) : step.status === 'running' ? (
                          <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
                        ) : (
                          <div className="w-3 h-3 border-2 border-gray-300 rounded-full flex-shrink-0"></div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium break-words">
                            Step {index + 1}: {step.step_id || `Step ${index + 1}`}
                          </div>
                          {step.tasks && step.tasks.length > 0 && (
                            <div className="text-gray-600 dark:text-gray-400 mt-1 break-words">
                              {step.tasks.length} task{step.tasks.length > 1 ? 's' : ''}: {step.tasks.map((task: any, taskIndex: number) =>
                                `${task.agent || 'Agent'} (${task.tool || 'Tool'})`
                              ).join(', ')}
                            </div>
                          )}
                        </div>
                        <div className={`text-xs px-2 py-1 rounded ${
                          step.status === 'completed'
                            ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300'
                            : step.status === 'running'
                            ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                            : 'bg-gray-100 dark:bg-gray-900 text-gray-700 dark:text-gray-300'
                        }`}>
                          {step.status || 'pending'}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      No steps available yet
                    </div>
                  )}
                </div>

                <div className="mt-3 pt-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-xs space-y-1">
                    <div>Total Steps: {planningData.execution_plan.total_steps || 0}</div>
                    <div>Current Step: {planningData.execution_plan.current_step || 0}</div>
                    <div>Status: {planningData.execution_plan.aggregate_status || 'pending'}</div>
                  </div>
                </div>
              </div>
            )}

            {planningData.semantic_routing && (
              <div className="bg-white dark:bg-gray-800 rounded p-3 border">
                <h4 className="font-medium text-sm mb-2">Semantic Routing</h4>
                <div className="text-xs">
                  {planningData.semantic_routing.is_chitchat ? (
                    <span className="text-green-600">Chitchat detected - Direct response</span>
                  ) : (
                    <span className="text-blue-600">Complex query - Multi-agent execution</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  const renderExecutionSection = () => {
    if (!executionData) return null

    return (
      <div className="border border-green-200 rounded-lg p-3 mb-3 bg-green-50 dark:bg-green-950">
        <div className="flex items-center gap-2 text-green-700 dark:text-green-300 font-medium mb-2">
          <Clock size={16} />
          <span>Executing Plan</span>
          {progress && (
            <span className="text-xs bg-green-200 dark:bg-green-800 px-2 py-1 rounded">
              {progress}%
            </span>
          )}
        </div>

        {isExecutionExpanded && (
          <div className="space-y-2">
            {executionData.agent_responses?.map((response, index) => (
              <div key={index} className="flex items-center gap-2 bg-white dark:bg-gray-800 rounded p-2 border text-xs">
                <CheckCircle size={12} className="text-green-600" />
                <span className="font-medium">{response.agent || 'Agent'}</span>
                <span className="text-gray-600 dark:text-gray-400">
                  {response.tool || 'Tool'} - {response.status || 'Completed'}
                </span>
              </div>
            ))}

            {executionData.current_step_results?.map((step, index) => (
              <div key={index} className="flex items-center gap-2 bg-white dark:bg-gray-800 rounded p-2 border text-xs">
                <AlertCircle size={12} className="text-yellow-600" />
                <span>Step {index + 1}: {step.description || 'Processing...'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div ref={messageRef} className="flex items-start gap-3">
      <div className="flex-1 space-y-2">
        {/* Planning Section */}
        {renderPlanningSection()}

        {/* Execution Section */}
        {renderExecutionSection()}

        {/* Main Content */}
        {(content || isStreaming) && (
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <MarkdownMessage content={displayedContent} onDocumentClick={onDocumentClick} />
          </div>
        )}

        {/* Thinking Indicator - show when streaming and processing */}
        {isStreaming && (
          <div className="mt-3 relative">
            <ThinkingIndicator
              planningData={planningData}
              executionData={executionData}
              progress={progress}
            />
          </div>
        )}
      </div>
    </div>
  )
}
