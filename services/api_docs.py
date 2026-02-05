# -*- coding: utf-8 -*-
"""
API 文档模块 (Swagger/OpenAPI)

使用 Flask-RESTX 提供交互式 API 文档
访问 /docs 查看 Swagger UI
"""
from flask import Blueprint
from flask_restx import Api, Resource, fields

# 创建蓝图
api_bp = Blueprint('api_docs', __name__)

# 创建 API 实例
api = Api(
    api_bp,
    version='1.0',
    title='A.VISION API',
    description='智能辅助视觉系统后端 API 文档',
    doc='/docs'  # Swagger UI 路径
)

# 定义命名空间
ns = api.namespace('', description='核心 API 端点')

# ========================
# 响应模型定义
# ========================
health_model = api.model('Health', {
    'ok': fields.Boolean(description='服务是否正常', example=True)
})

box_model = api.model('Box', {
    'label': fields.String(description='检测到的物体标签', example='person'),
    'conf': fields.Float(description='置信度 (0-1)', example=0.87),
    'x1': fields.Float(description='边界框左上角 X'),
    'y1': fields.Float(description='边界框左上角 Y'),
    'x2': fields.Float(description='边界框右下角 X'),
    'y2': fields.Float(description='边界框右下角 Y'),
})

alert_model = api.model('Alert', {
    'level': fields.Integer(description='警报等级 (0=无, 1=关注, 2=警惕, 3=危险)', example=0),
    'text': fields.String(description='警报文本', example=''),
    'target': fields.Raw(description='触发警报的目标对象', example=None),
})

voice_log_model = api.model('VoiceLog', {
    'role': fields.String(description='角色 (user/ai)', example='user'),
    'content': fields.String(description='内容', example='前面有什么？'),
    'ts': fields.Float(description='时间戳 (UNIX)')
})

voice_model = api.model('Voice', {
    'status': fields.String(description='语音助手状态', example='idle'),
    'logs': fields.List(fields.Nested(voice_log_model), description='语音交互日志'),
    'ts': fields.Float(description='最后更新时间戳')
})

search_model = api.model('Search', {
    'active': fields.Boolean(description='是否处于寻物模式', example=False),
    'target_class': fields.String(description='目标 COCO 类名', example=''),
    'target_label': fields.String(description='目标中文名', example=''),
    'target_info': fields.Raw(description='目标位置信息', example=None)
})

detect_model = api.model('Detect', {
    'boxes': fields.List(fields.Nested(box_model), description='检测到的边界框列表'),
    'shape': fields.List(fields.Integer, description='画面尺寸 [高, 宽]', example=[480, 640]),
    'fps': fields.Float(description='当前帧率', example=20.5),
    'infer_ms': fields.Float(description='推理耗时 (毫秒)', example=45.2),
    'delay': fields.Float(description='端到端延迟 (毫秒)', example=120.0),
    'last_update': fields.Float(description='最后更新时间戳'),
    'alert': fields.Nested(alert_model, description='当前警报状态'),
    'audio_ok': fields.Boolean(description='音频服务是否正常'),
    'voice': fields.Nested(voice_model, description='语音助手状态'),
    'search': fields.Nested(search_model, description='寻物模式状态')
})


# ========================
# API 端点
# ========================
@ns.route('/health')
class HealthResource(Resource):
    @ns.doc('health_check')
    @ns.marshal_with(health_model)
    def get(self):
        """健康检查
        
        返回服务运行状态。可用于负载均衡器健康检查。
        """
        return {'ok': True}


@ns.route('/detect')
class DetectResource(Resource):
    @ns.doc('get_detection')
    @ns.marshal_with(detect_model)
    def get(self):
        """获取检测数据
        
        返回当前的视觉检测结果、系统指标和警报状态。
        前端应周期性轮询此接口 (建议间隔 250ms)。
        """
        # 注意：这里只是定义文档，实际路由在 main.py 中
        # 返回空对象用于 Swagger 文档生成
        return {}


@ns.route('/video')
class VideoResource(Resource):
    @ns.doc('video_stream')
    @ns.produces(['multipart/x-mixed-replace'])
    def get(self):
        """MJPEG 视频流
        
        返回持续的 MJPEG 视频流。
        在前端中使用 `<img src="/video">` 嵌入。
        
        **注意**: 此端点返回持续的流式响应，不适合在 Swagger UI 中测试。
        """
        return {'message': 'MJPEG stream - 请在浏览器中直接访问或使用 <img> 标签'}


def init_api_docs(app):
    """将 API 文档蓝图注册到 Flask 应用"""
    app.register_blueprint(api_bp, url_prefix='/api')
    print("API 文档已启用: http://localhost:5000/api/docs")
