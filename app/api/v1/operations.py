"""
Operations APIs: dashboard, data health and exports.
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_permission
from app.models.user import User
from app.services import operations_service
from app.utils.response import success

router = APIRouter(prefix="/operations", tags=["运营工作台"])


@router.get("/dashboard")
def dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(data=operations_service.dashboard_summary(user, db))


@router.get("/data-health")
def data_health(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(data=operations_service.data_health(user, db))


@router.get("/exports/{export_type}")
def export_data(
    export_type: str,
    student_id: int = Query(None),
    user: User = Depends(require_permission("operations:export")),
    db: Session = Depends(get_db),
):
    filename, content = operations_service.export_csv(export_type, user, db, student_id=student_id)
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
