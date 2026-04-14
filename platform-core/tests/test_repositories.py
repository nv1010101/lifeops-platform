from __future__ import annotations

import uuid

from app.repositories.base import BaseRepository
from app.spaces.models import Space, SpaceType
from app.users.models import User


async def test_user_repository_smoke(migrated_session) -> None:
    repository = BaseRepository(migrated_session, User)
    user = User(email="repo-user@example.com", hashed_password="hashed-value")

    saved_user = await repository.save(user)
    await migrated_session.commit()

    loaded_user = await repository.get_by_id(saved_user.id)

    assert loaded_user is not None
    assert loaded_user.id == saved_user.id
    assert loaded_user.email == "repo-user@example.com"


async def test_space_repository_smoke(migrated_session) -> None:
    user_repository = BaseRepository(migrated_session, User)
    owner = await user_repository.save(
        User(email=f"space-owner-{uuid.uuid4().hex}@example.com", hashed_password="hashed-value")
    )

    space_repository = BaseRepository(migrated_session, Space)
    space = Space(name="Owner Space", type=SpaceType.PERSONAL, owner_id=owner.id)

    saved_space = await space_repository.save(space)
    await migrated_session.commit()

    loaded_space = await space_repository.get_by_id(saved_space.id)

    assert loaded_space is not None
    assert loaded_space.id == saved_space.id
    assert loaded_space.owner_id == owner.id
    assert loaded_space.type is SpaceType.PERSONAL
