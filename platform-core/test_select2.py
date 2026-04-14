from sqlalchemy import select
from app.model_registry import load_all_models
from app.users.models import User
from app.memberships.models import Membership
from app.spaces.isolation import assert_space_scope
import uuid

load_all_models()
q = select(User, Membership).join(Membership)
try:
    assert_space_scope(q, uuid.uuid4())
    print("Success")
except ValueError as e:
    print(f"Error: {e}")
