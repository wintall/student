import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.exceptions import PermissionDenied
from app.models.user import User
from app.services.nl_db_service import execute_tool_call
from app.services.nl_db_tools import check_permission, get_user_permission_list
from app.services.operations_service import export_csv


def test_student_cannot_export_teachers_but_can_export_own_transcript():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "student01").first()
        assert user is not None

        denied = False
        try:
            export_csv("teachers", user, db)
        except PermissionDenied:
            denied = True
        assert denied is True

        filename, content = export_csv("transcript", user, db)
        assert filename == "transcript.csv"
        assert isinstance(content, str)

        assert check_permission(user, db, "teacher:query") is False
        assert "teacher:query" not in get_user_permission_list(user, db)
        tool_result = execute_tool_call("query_teacher", {}, user, db)
        assert tool_result["success"] is False
        assert "people:teacher:list" in tool_result["message"]
    finally:
        db.close()


if __name__ == "__main__":
    test_student_cannot_export_teachers_but_can_export_own_transcript()
    print("PASS test_student_cannot_export_teachers_but_can_export_own_transcript")
