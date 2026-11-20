"""Bündelt alle internen API-Routen."""

from api.accounts import routes as account_routes
from api.budgets import routes as budget_routes
from api.categories import routes as category_routes
from api.recurring import routes as recurring_routes
from api.salary import routes as salary_routes
from api.stats import routes as stats_routes
from api.transactions import routes as transaction_routes
from api.transfers import routes as transfer_routes

routes = [
    *account_routes,
    *category_routes,
    *transaction_routes,
    *transfer_routes,
    *budget_routes,
    *recurring_routes,
    *salary_routes,
    *stats_routes,
]
