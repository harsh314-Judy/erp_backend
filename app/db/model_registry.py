"""Import every table model so SQLModel.metadata is complete for Alembic."""


def import_models() -> None:
    from app.api.routes.auth import auth_model as auth_model
    from app.api.routes.customer import customer_model as customer_model
    from app.api.routes.operation import operation_model as operation_model
    from app.api.routes.product import product_model as product_model
    from app.api.routes.production import production_model as production_model
    from app.api.routes.purchase_order import purchase_order_model as purchase_order_model
    from app.api.routes.raw_material import raw_material_model as raw_material_model
    from app.api.routes.sales import sales_model as sales_model
    from app.api.routes.supplier import supplier_model as supplier_model
    from app.api.routes.user import user_model as user_model
