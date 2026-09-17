from logger import logger
from controller.auth_controller import AuthController


class HardwareAuthController(AuthController):
    """Authentication controller for the Engineering Equipment Tracking System."""

    def __init__(self, db_name="hardware_inventory.db"):
        super().__init__(db_name=db_name)

    def login(self, username, password):
        success, msg = super().login(username, password)
        if not success:
            logger.warning(f"Failed login attempt for username: '{username}' - {msg}")
        return success, msg

    def register(self, username, password, email=None, role="USER"):
        success, msg = super().register(username, password, email=email, role=role)
        if not success:
            logger.warning(f"Failed registration attempt for username: '{username}', email: '{email}' - {msg}")
        else:
            logger.info(f"Successful registration: username='{username}', email='{email}'")
        return success, msg

    def logout(self, username="Unknown"):
        logger.info(f"User Logged Out: '{username}' logged out.")
        return True, "Logged out successfully."
