import json
from datetime import datetime

import pytest

from errors import ErrorCodes
from lib.response import StandardResponse
from model.users.dto import UserOut
from sqlc.users import GetUserRow


def test_error_codes_render_their_label_status_and_message():
    response = StandardResponse(ErrorCodes.AdminRequired).nolog_error()

    assert response.status_code == 403
    assert json.loads(response.body) == {
        "errcode": "AdminRequired",
        "detail": "admin role required",
    }


def test_success_keeps_the_plain_message():
    response = StandardResponse("ok", {"id": 1}).success(201)

    assert response.status_code == 201
    assert json.loads(response.body) == {"detail": "ok", "data": {"id": 1}}


def test_success_encodes_pydantic_models():
    user = UserOut.model_validate(
        GetUserRow(
            id_=1,
            username="ada",
            phone_number=None,
            email="ada@example.com",
            role="user",
            created_at=datetime(2024, 1, 2, 3, 4, 5),
        )
    )

    response = StandardResponse("ok", user).success()

    assert json.loads(response.body) == {
        "detail": "ok",
        "data": {
            "id_": 1,
            "username": "ada",
            "email": "ada@example.com",
            "phone_number": None,
            "role": "user",
            "created_at": "2024-01-02T03:04:05",
        },
    }


def test_the_error_path_rejects_plain_strings():
    with pytest.raises(TypeError):
        StandardResponse("ok").nolog_error()


def test_every_label_is_unique():
    labels = [
        value.label
        for value in vars(ErrorCodes).values()
        if hasattr(value, "label")
    ]

    assert len(labels) == len(set(labels))
