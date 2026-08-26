import unittest

from app.routers.auth import _public_user


class PublicUserResponseTests(unittest.TestCase):
    def test_admin_permissions_are_available_immediately_after_login(self):
        user = _public_user({
            "id": 7,
            "username": "campus_admin",
            "nickname": "管理员",
            "is_admin": 1,
        })

        self.assertTrue(user["is_admin"])
        self.assertFalse(user["is_root"])

    def test_root_is_identified_without_requiring_admin_column(self):
        user = _public_user({"id": 1, "username": "root", "is_admin": 0})

        self.assertTrue(user["is_root"])


if __name__ == "__main__":
    unittest.main()
