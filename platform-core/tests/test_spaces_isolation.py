import uuid
import pytest
from sqlalchemy import select

from app.spaces.isolation import assert_space_scope
from app.users.models import User
from app.memberships.models import Membership
from app.dashboard.models import DashboardPreference

def test_assert_space_scope_with_valid_entity():
    """Тест проверяет, что фильтр добавляется, если в запросе есть сущность с space_id."""
    space_id = uuid.uuid4()
    query = select(Membership)
    scoped_query = assert_space_scope(query, space_id)
    
    # Проверяем, что запрос был изменен и содержит условие
    assert str(space_id).replace("-", "") in str(scoped_query.compile(compile_kwargs={"literal_binds": True})).replace("-", "")
    assert "space_id =" in str(scoped_query.compile())

def test_assert_space_scope_with_joined_query():
    """Тест проверяет работу с join-запросами."""
    space_id = uuid.uuid4()
    query = select(User, Membership).join(Membership)
    scoped_query = assert_space_scope(query, space_id)
    
    assert str(space_id).replace("-", "") in str(scoped_query.compile(compile_kwargs={"literal_binds": True})).replace("-", "")

def test_assert_space_scope_with_specific_column():
    """Тест проверяет, что извлечение работает даже при выборе конкретных колонок сущности с space_id."""
    space_id = uuid.uuid4()
    query = select(DashboardPreference.config)
    scoped_query = assert_space_scope(query, space_id)
    
    assert str(space_id).replace("-", "") in str(scoped_query.compile(compile_kwargs={"literal_binds": True})).replace("-", "")

def test_assert_space_scope_missing_space_id():
    """Тест проверяет, что будет ошибка, если в запросе нет сущности с space_id."""
    space_id = uuid.uuid4()
    query = select(User)
    
    with pytest.raises(ValueError, match="Query must select a mapped entity with a space_id column"):
        assert_space_scope(query, space_id)

def test_assert_space_scope_empty_query():
    """Тест проверяет ошибку при пустом select()."""
    space_id = uuid.uuid4()
    # Создаем фиктивный запрос без колонок (что редко бывает в реальности, но мы проверяем логику)
    query = select()
    
    with pytest.raises(ValueError, match="Query must select at least one mapped entity"):
        assert_space_scope(query, space_id)
