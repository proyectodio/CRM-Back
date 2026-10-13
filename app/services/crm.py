from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.db.models import (
    AccountModel,
    ActivityModel,
    ContactModel,
    CustomFieldModel,
    CustomFieldValueModel,
    LeadModel,
    OpportunityModel,
    PipelineModel,
    ProductModel,
    QuoteItemModel,
    QuoteModel,
    StageModel,
    TenantModel,
    UserModel,
)

MONEY = Decimal("0.01")
ADMIN_ROLES = {"owner", "admin"}
WRITE_ROLES = {"owner", "admin", "sales"}
LEAD_STATUSES = {"new", "contacted", "qualified", "unqualified", "converted"}
ACTIVITY_KINDS = {"task", "call", "meeting"}
QUOTE_STATUSES = {"draft", "sent", "accepted", "rejected", "expired"}
ENTITY_TYPES = {"account", "contact", "lead", "opportunity"}
FIELD_TYPES = {"text", "number", "date", "boolean", "select"}
DEFAULT_STAGES = (
    ("Nuevo", 1, 10, "open"),
    ("Calificación", 2, 30, "open"),
    ("Propuesta", 3, 50, "open"),
    ("Negociación", 4, 75, "open"),
    ("Ganada", 5, 100, "won"),
    ("Perdida", 6, 0, "lost"),
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "empresa"


def require_write(user: UserModel) -> None:
    if user.role not in WRITE_ROLES:
        raise ForbiddenError("Este rol solo puede consultar información")


def require_admin(user: UserModel) -> None:
    if user.role not in ADMIN_ROLES:
        raise ForbiddenError("Solo un administrador puede cambiar esta configuración")


def owned(session: Session, model, record_id: int, tenant_id: int):
    row = session.get(model, record_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError("Registro no encontrado")
    return row


def list_owned(session: Session, model, tenant_id: int):
    stmt = select(model).where(model.tenant_id == tenant_id).order_by(model.id.desc())
    return list(session.scalars(stmt).all())


def create_company(
    session: Session,
    *,
    company_name: str,
    name: str,
    email: str,
    password: str,
) -> tuple[TenantModel, UserModel]:
    normalized_email = email.lower().strip()
    existing = session.scalar(select(UserModel).where(UserModel.email == normalized_email))
    if existing is not None:
        raise ConflictError("Ya existe un usuario con ese correo")

    base_slug = slugify(company_name)
    slug = base_slug
    suffix = 2
    while session.scalar(select(TenantModel).where(TenantModel.slug == slug)):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    moment = now()
    tenant = TenantModel(
        name=company_name.strip(),
        slug=slug,
        is_active=True,
        created_at=moment,
        updated_at=moment,
    )
    session.add(tenant)
    session.flush()
    user = UserModel(
        tenant_id=tenant.id,
        name=name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        role="owner",
        is_active=True,
        created_at=moment,
        updated_at=moment,
    )
    pipeline = PipelineModel(
        tenant_id=tenant.id,
        name="Comercial",
        is_default=True,
        created_at=moment,
        updated_at=moment,
    )
    session.add_all([user, pipeline])
    session.flush()
    for stage_name, position, probability, outcome in DEFAULT_STAGES:
        session.add(
            StageModel(
                tenant_id=tenant.id,
                pipeline_id=pipeline.id,
                name=stage_name,
                position=position,
                probability=probability,
                outcome=outcome,
                created_at=moment,
                updated_at=moment,
            )
        )
    session.commit()
    session.refresh(user)
    session.refresh(tenant)
    return tenant, user


def add_user(session: Session, actor: UserModel, *, name: str, email: str, password: str, role: str) -> UserModel:
    require_admin(actor)
    normalized_email = email.lower().strip()
    if session.scalar(select(UserModel).where(UserModel.email == normalized_email)):
        raise ConflictError("Ya existe un usuario con ese correo")
    moment = now()
    user = UserModel(
        tenant_id=actor.tenant_id,
        name=name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        created_at=moment,
        updated_at=moment,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def default_pipeline(session: Session, tenant_id: int) -> PipelineModel:
    pipeline = session.scalar(
        select(PipelineModel).where(
            PipelineModel.tenant_id == tenant_id,
            PipelineModel.is_default.is_(True),
        )
    )
    if pipeline is None:
        raise NotFoundError("La empresa no tiene un pipeline comercial")
    return pipeline


def first_open_stage(session: Session, tenant_id: int, pipeline_id: int) -> StageModel:
    stage = session.scalar(
        select(StageModel)
        .where(
            StageModel.tenant_id == tenant_id,
            StageModel.pipeline_id == pipeline_id,
            StageModel.outcome == "open",
        )
        .order_by(StageModel.position.asc())
    )
    if stage is None:
        raise NotFoundError("El pipeline no tiene una etapa abierta")
    return stage


def status_for_stage(stage: StageModel) -> str:
    if stage.outcome == "won":
        return "won"
    if stage.outcome == "lost":
        return "lost"
    return "open"


def create_opportunity(
    session: Session,
    actor: UserModel,
    *,
    title: str,
    amount: Decimal,
    currency: str,
    pipeline_id: int | None,
    stage_id: int | None,
    account_id: int | None,
    contact_id: int | None,
    lead_id: int | None,
    expected_close_date,
    notes: str | None,
) -> OpportunityModel:
    require_write(actor)
    pipeline = (
        owned(session, PipelineModel, pipeline_id, actor.tenant_id)
        if pipeline_id
        else default_pipeline(session, actor.tenant_id)
    )
    if stage_id:
        stage = owned(session, StageModel, stage_id, actor.tenant_id)
        if stage.pipeline_id != pipeline.id:
            raise ConflictError("La etapa no pertenece a ese pipeline")
    else:
        stage = first_open_stage(session, actor.tenant_id, pipeline.id)
    if account_id:
        owned(session, AccountModel, account_id, actor.tenant_id)
    if contact_id:
        owned(session, ContactModel, contact_id, actor.tenant_id)
    if lead_id:
        owned(session, LeadModel, lead_id, actor.tenant_id)
    moment = now()
    row = OpportunityModel(
        tenant_id=actor.tenant_id,
        pipeline_id=pipeline.id,
        stage_id=stage.id,
        account_id=account_id,
        contact_id=contact_id,
        lead_id=lead_id,
        owner_id=actor.id,
        title=title.strip(),
        amount=money(amount),
        currency=currency.upper(),
        expected_close_date=expected_close_date,
        status=status_for_stage(stage),
        notes=notes,
        created_at=moment,
        updated_at=moment,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def move_opportunity(session: Session, actor: UserModel, opportunity_id: int, stage_id: int) -> OpportunityModel:
    require_write(actor)
    opportunity = owned(session, OpportunityModel, opportunity_id, actor.tenant_id)
    stage = owned(session, StageModel, stage_id, actor.tenant_id)
    if stage.pipeline_id != opportunity.pipeline_id:
        raise ConflictError("La etapa no pertenece al pipeline de la oportunidad")
    opportunity.stage_id = stage.id
    opportunity.status = status_for_stage(stage)
    opportunity.updated_at = now()
    session.commit()
    session.refresh(opportunity)
    return opportunity


def convert_lead(session: Session, actor: UserModel, lead_id: int) -> OpportunityModel:
    require_write(actor)
    lead = owned(session, LeadModel, lead_id, actor.tenant_id)
    if lead.status == "converted":
        raise ConflictError("El prospecto ya fue convertido")
    pipeline = default_pipeline(session, actor.tenant_id)
    stage = first_open_stage(session, actor.tenant_id, pipeline.id)
    moment = now()
    opportunity = OpportunityModel(
        tenant_id=actor.tenant_id,
        pipeline_id=pipeline.id,
        stage_id=stage.id,
        account_id=lead.account_id,
        contact_id=lead.contact_id,
        lead_id=lead.id,
        owner_id=actor.id,
        title=lead.title,
        amount=Decimal("0.00"),
        currency="USD",
        expected_close_date=None,
        status="open",
        notes=lead.notes,
        created_at=moment,
        updated_at=moment,
    )
    lead.status = "converted"
    lead.updated_at = moment
    session.add(opportunity)
    session.commit()
    session.refresh(opportunity)
    return opportunity


def quote_lines(session: Session, actor: UserModel, items: list[dict]) -> list[dict]:
    if not items:
        raise ConflictError("La cotización necesita al menos un concepto")
    priced: list[dict] = []
    for item in items:
        quantity = money(Decimal(item["quantity"]))
        if quantity <= 0:
            raise ConflictError("La cantidad debe ser mayor que cero")
        product_id = item.get("product_id")
        if product_id:
            product = owned(session, ProductModel, product_id, actor.tenant_id)
            if not product.is_active:
                raise ConflictError("El producto o servicio no está activo")
            unit_price = money(Decimal(product.unit_price))
            description = product.name
        else:
            description = (item.get("description") or "").strip()
            if not description:
                raise ConflictError("Un concepto sin producto necesita descripción")
            unit_price = money(Decimal(item["unit_price"]))
        discount = money(Decimal(item.get("discount") or 0))
        gross = money(quantity * unit_price)
        if discount < 0 or discount > gross:
            raise ConflictError("El descuento no puede superar el importe del concepto")
        priced.append(
            {
                "product_id": product_id,
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount": discount,
                "line_total": money(gross - discount),
                "gross": gross,
            }
        )
    return priced


def create_quote(session: Session, actor: UserModel, payload: dict) -> QuoteModel:
    require_write(actor)
    owned(session, AccountModel, payload["account_id"], actor.tenant_id)
    if payload.get("opportunity_id"):
        owned(session, OpportunityModel, payload["opportunity_id"], actor.tenant_id)
    lines = quote_lines(session, actor, payload["items"])
    subtotal = money(sum((line["gross"] for line in lines), Decimal("0")))
    total = money(sum((line["line_total"] for line in lines), Decimal("0")))
    last_id = session.scalar(select(func.max(QuoteModel.id)).where(QuoteModel.tenant_id == actor.tenant_id))
    number = f"COT-{(last_id or 0) + 1:04d}"
    moment = now()
    quote = QuoteModel(
        tenant_id=actor.tenant_id,
        account_id=payload["account_id"],
        opportunity_id=payload.get("opportunity_id"),
        number=number,
        status="draft",
        currency=payload["currency"].upper(),
        valid_until=payload.get("valid_until"),
        notes=payload.get("notes"),
        subtotal=subtotal,
        total=total,
        created_at=moment,
        updated_at=moment,
    )
    session.add(quote)
    session.flush()
    for line in lines:
        session.add(
            QuoteItemModel(
                tenant_id=actor.tenant_id,
                quote_id=quote.id,
                product_id=line["product_id"],
                description=line["description"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                discount=line["discount"],
                line_total=line["line_total"],
            )
        )
    session.commit()
    session.refresh(quote)
    return quote


def dashboard(session: Session, tenant_id: int) -> dict:
    def count(model, *filters):
        stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id, *filters)
        return int(session.scalar(stmt) or 0)

    pipeline_amount = session.scalar(
        select(func.coalesce(func.sum(OpportunityModel.amount), 0)).where(
            OpportunityModel.tenant_id == tenant_id,
            OpportunityModel.status == "open",
        )
    )
    return {
        "accounts": count(AccountModel),
        "contacts": count(ContactModel),
        "open_leads": count(LeadModel, LeadModel.status.notin_(["converted", "unqualified"])),
        "open_opportunities": count(OpportunityModel, OpportunityModel.status == "open"),
        "pipeline_amount": money(Decimal(pipeline_amount or 0)),
        "open_activities": count(ActivityModel, ActivityModel.completed_at.is_(None)),
        "open_quotes": count(QuoteModel, QuoteModel.status.in_(["draft", "sent"])),
    }


def add_stage(session: Session, actor: UserModel, pipeline_id: int, *, name: str, probability: int, outcome: str) -> StageModel:
    require_admin(actor)
    pipeline = owned(session, PipelineModel, pipeline_id, actor.tenant_id)
    last_position = session.scalar(
        select(func.max(StageModel.position)).where(StageModel.pipeline_id == pipeline.id)
    )
    moment = now()
    stage = StageModel(
        tenant_id=actor.tenant_id,
        pipeline_id=pipeline.id,
        name=name.strip(),
        position=int(last_position or 0) + 1,
        probability=probability,
        outcome=outcome,
        created_at=moment,
        updated_at=moment,
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage
