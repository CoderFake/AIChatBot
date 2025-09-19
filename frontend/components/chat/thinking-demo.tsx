"use client"

import { ThinkingIndicator } from "./streaming-message"

export function ThinkingDemo() {
  const samplePlanningData = {
    semantic_routing: {
      is_chitchat: false
    },
    execution_plan: {
      total_steps: 5,
      execution_flow: {
        planning: {
          tasks: [
            { id: 1, description: "Analyze user query" },
            { id: 2, description: "Route to appropriate agents" },
            { id: 3, description: "Execute agent tasks" }
          ]
        }
      }
    }
  }

  const sampleExecutionData = {
    agent_responses: [
      { agent: "SearchAgent", tool: "WebSearch", status: "Completed" },
      { agent: "AnalysisAgent", tool: "DataAnalysis", status: "Processing" }
    ],
    current_step_results: [
      { description: "Searching for relevant information..." },
      { description: "Analyzing search results..." }
    ]
  }

  return (
    <div className="p-8 space-y-6">
      <div className="space-y-4">
        <div className="p-4 bg-white dark:bg-gray-900 rounded-lg">
          <ThinkingIndicator />
        </div>

        <div className="p-4 bg-white dark:bg-gray-900 rounded-lg relative">
          <ThinkingIndicator
            planningData={samplePlanningData}
            executionData={sampleExecutionData}
            progress={75}
          />
        </div>

        <div className="max-w-md">
          <div className="flex gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-medium">
              AI
            </div>
            <div className="flex-1">
              <div className="mt-3 relative">
                <ThinkingIndicator
                  planningData={samplePlanningData}
                  executionData={sampleExecutionData}
                  progress={45}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-900 rounded-lg relative">
          <ThinkingIndicator progress={25} />
        </div>
      </div>
    </div>
  )
}
