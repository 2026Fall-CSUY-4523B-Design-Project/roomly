"""Controllers: one APIRouter per use case of SSDS §8.1.2, registered in this order."""

from roomly.controller import (
    account_controller,
    admin_controller,
    comparison_controller,
    group_controller,
    listing_controller,
    notification_controller,
    room_controller,
    search_controller,
)

ROUTERS = [
    account_controller.router,
    group_controller.router,
    listing_controller.router,
    admin_controller.router,
    search_controller.router,
    comparison_controller.router,
    room_controller.router,
    notification_controller.router,
]
