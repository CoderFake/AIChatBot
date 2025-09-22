from enum import Enum
from common.types import DocumentAccessLevel as CommonDocumentAccessLevel, DBDocumentPermissionLevel as CommonDBDocumentPermissionLevel


class RoleTypes(str, Enum):
    MAINTAINER = "MAINTAINER"
    ADMIN = "ADMIN"
    DEPT_ADMIN = "DEPT_ADMIN"
    DEPT_MANAGER = "DEPT_MANAGER"
    USER = "USER"


DocumentAccessLevel = CommonDocumentAccessLevel
DBDocumentPermissionLevel = CommonDBDocumentPermissionLevel


# Language Detection Mappings
LANGUAGE_MAPPING = {
    'vi': 'vietnamese',
    'en': 'english',
    'ja': 'japanese',
    'ko': 'korean',
}

# Supported Languages
SUPPORTED_LANGUAGES = ['vietnamese', 'english', 'chinese', 'japanese', 'korean']

# Localized Messages for System
LOCALIZED_MESSAGES = {
    # Generic system messages
    "system_error": {
        "vietnamese": "Lỗi hệ thống",
        "english": "System error",
        "chinese": "系统错误",
        "japanese": "システムエラー",
        "korean": "시스템 오류"
    },
    "processing_completed": {
        "vietnamese": "Hoàn thành xử lý",
        "english": "Processing completed",
        "chinese": "处理完成",
        "japanese": "処理完了",
        "korean": "처리 완료"
    },
    "no_results": {
        "vietnamese": "Không có kết quả",
        "english": "No results found",
        "chinese": "未找到结果",
        "japanese": "結果が見つかりません",
        "korean": "결과를 찾을 수 없습니다"
    },
    "error_occurred": {
        "vietnamese": "Đã xảy ra lỗi: {error}",
        "english": "An error occurred: {error}",
        "chinese": "发生错误：{error}",
        "japanese": "エラーが発生しました：{error}",
        "korean": "오류가 발생했습니다: {error}"
    },
    "execution_plan_ready": {
        "vietnamese": "Kế hoạch thực hiện đã sẵn sàng",
        "english": "Execution plan is ready",
        "chinese": "执行计划已准备就绪",
        "japanese": "実行計画の準備ができました",
        "korean": "실행 계획이 준비되었습니다"
    },
    "executing_task": {
        "vietnamese": "Đang thực hiện tác vụ {current}/{total}: {agent} với {tool}",
        "english": "Executing task {current}/{total}: {agent} with {tool}",
        "chinese": "正在执行任务 {current}/{total}：{agent} 使用 {tool}",
        "japanese": "タスクを実行中 {current}/{total}：{agent} が {tool} を使用",
        "korean": "작업 실행 중 {current}/{total}: {agent}이(가) {tool} 사용"
    },
    "task_completed_sequential": {
        "vietnamese": "Hoàn thành tác vụ {current}/{total}: {agent} với {tool}",
        "english": "Completed task {current}/{total}: {agent} with {tool}",
        "chinese": "完成任务 {current}/{total}：{agent} 使用 {tool}",
        "japanese": "タスク完了 {current}/{total}：{agent} が {tool} を使用",
        "korean": "작업 완료 {current}/{total}: {agent}이(가) {tool} 사용"
    }
}

# Workflow-specific Messages
WORKFLOW_MESSAGES = {
    # Orchestrator messages
    "starting_analysis": {
        "vietnamese": "Bắt đầu phân tích câu hỏi",
        "english": "Starting query analysis",
        "chinese": "开始分析查询",
        "japanese": "クエリ分析を開始",
        "korean": "쿼리 분석 시작"
    },

    # Planning messages
    "planning_created": {
        "vietnamese": "Đã tạo kế hoạch thực thi với {total_steps} bước",
        "english": "Created execution plan with {total_steps} steps",
        "chinese": "创建了包含{total_steps}步骤的执行计划",
        "japanese": "{total_steps}ステップの実行プランを作成しました",
        "korean": "{total_steps}단계의 실행 계획을 생성했습니다"
    },
    "chitchat_response": {
        "vietnamese": "Phản hồi chitchat",
        "english": "Chitchat response",
        "chinese": "闲聊响应",
        "japanese": "雑談応答",
        "korean": "잡담 응답"
    },

    # Progress messages
    "completed": {
        "vietnamese": "Hoàn thành",
        "english": "Completed",
        "chinese": "完成",
        "japanese": "完了",
        "korean": "완료"
    },

    # Sequential execution messages
    "execution_plan_ready": {
        "vietnamese": "Kế hoạch thực hiện đã sẵn sàng",
        "english": "Execution plan is ready",
        "chinese": "执行计划已准备就绪",
        "japanese": "実行計画の準備ができました",
        "korean": "실행 계획이 준비되었습니다"
    },
    "executing_task": {
        "vietnamese": "Đang thực hiện tác vụ {current}/{total}: {agent} với {tool}",
        "english": "Executing task {current}/{total}: {agent} with {tool}",
        "chinese": "正在执行任务 {current}/{total}：{agent} 使用 {tool}",
        "japanese": "タスクを実行中 {current}/{total}：{agent} が {tool} を使用",
        "korean": "작업 실행 중 {current}/{total}: {agent}이(가) {tool} 사용"
    },
    "task_completed_sequential": {
        "vietnamese": "Hoàn thành tác vụ {current}/{total}: {agent} với {tool}",
        "english": "Completed task {current}/{total}: {agent} with {tool}",
        "chinese": "完成任务 {current}/{total}：{agent} 使用 {tool}",
        "japanese": "タスク完了 {current}/{total}：{agent} が {tool} を使用",
        "korean": "작업 완료 {current}/{total}: {agent}이(가) {tool} 사용"
    },
    "task_recovered": {
        "vietnamese": "Hoàn thành tác vụ {current}/{total}: {agent} với {tool} sau {attempts} lần thử",
        "english": "Completed task {current}/{total}: {agent} with {tool} after {attempts} attempts",
        "chinese": "完成任务 {current}/{total}：{agent} 使用 {tool}，在第 {attempts} 次尝试后",
        "japanese": "タスク完了 {current}/{total}：{agent} が {tool} を使用し {attempts} 回目の試行で達成",
        "korean": "작업 완료 {current}/{total}: {agent}이(가) {tool} 사용으로 {attempts}번째 시도 후 완료"
    },
    "task_retrying": {
        "vietnamese": "Tác vụ {agent} với {tool} gặp lỗi: {error}. Đang thử lại (lần {attempt}/{max_attempts}).",
        "english": "Task {agent} with {tool} hit an error: {error}. Retrying ({attempt}/{max_attempts}).",
        "chinese": "任务 {agent} 使用 {tool} 出现错误：{error}。正在重试（第 {attempt}/{max_attempts} 次）。",
        "japanese": "タスク {agent} が {tool} を使用中にエラー: {error}。再試行中 ({attempt}/{max_attempts})。",
        "korean": "작업 {agent}이(가) {tool} 사용 중 오류 발생: {error}. 재시도 중 ({attempt}/{max_attempts})."
    },
    "task_failed": {
        "vietnamese": "Tác vụ {agent} với {tool} thất bại: {error}",
        "english": "Task {agent} with {tool} failed: {error}",
        "chinese": "任务 {agent} 使用 {tool} 失败：{error}",
        "japanese": "タスク {agent} が {tool} を使用して失敗しました: {error}",
        "korean": "작업 {agent}이(가) {tool} 사용에 실패했습니다: {error}"
    },

    # Error messages
    "generic_error": {
        "vietnamese": "Xin lỗi, tôi gặp sự cố khi xử lý câu hỏi của bạn.",
        "english": "I'm sorry, I encountered an issue processing your question.",
        "chinese": "抱歉，处理您的问题时遇到了问题。",
        "japanese": "申し訳ございませんが、ご質問の処理中に問題が発生しました。",
        "korean": "죄송합니다. 질문을 처리하는 중에 문제가 발생했습니다."
    },
    "no_response": {
        "vietnamese": "Xin lỗi, tôi không thể tạo phản hồi cho câu hỏi của bạn.",
        "english": "I'm sorry, I couldn't create a response for your question.",
        "chinese": "抱歉，我无法为您的问题创建响应。",
        "japanese": "申し訳ございませんが、ご質問に対する応答を作成できませんでした。",
        "korean": "죄송합니다. 귀하의 질문에 대한 응답을 생성할 수 없습니다."
    },

    # Agent combination messages
    "no_agent_results": {
        "vietnamese": "Không có kết quả hợp lệ từ các agent.",
        "english": "No valid results from agents.",
        "chinese": "代理商没有有效结果。",
        "japanese": "エージェントから有効な結果がありません。",
        "korean": "에이전트에서 유효한 결과가 없습니다."
    },

    # Error handler messages
    "error_completion": {
        "vietnamese": "Hoàn thành với lỗi",
        "english": "Completed with errors",
        "chinese": "完成但有错误",
        "japanese": "エラーありで完了",
        "korean": "오류와 함께 완료"
    },

    # Workflow streaming messages
    "workflow_failed": {
        "vietnamese": "Workflow thất bại: {error}",
        "english": "Workflow failed: {error}",
        "chinese": "工作流失败：{error}",
        "japanese": "ワークフロー失敗：{error}",
        "korean": "워크플로 실패: {error}"
    }
}
