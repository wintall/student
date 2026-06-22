"""
全局异常类定义
"""


class BusinessException(Exception):
    """业务异常 - 返回具体错误信息"""
    def __init__(self, code: int = 400, message: str = "操作失败"):
        self.code = code
        self.message = message
        super().__init__(message)


class AuthenticationError(BusinessException):
    """认证异常"""
    def __init__(self, message: str = "认证失败"):
        super().__init__(code=401, message=message)


class PermissionDenied(BusinessException):
    """权限异常"""
    def __init__(self, message: str = "无权限执行此操作"):
        super().__init__(code=403, message=message)


class NotFoundError(BusinessException):
    """资源不存在"""
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=404, message=message)
