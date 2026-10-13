from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.api.v1.schemas import (
    AccountSchema,
    AccountWriteSchema,
    ActivitySchema,
    ActivityWriteSchema,
    ContactSchema,
    ContactWriteSchema,
    CustomFieldSchema,
    CustomFieldWriteSchema,
    CustomValueSchema,
    CustomValueWriteSchema,
    DashboardSchema,
    LeadSchema,
    LeadWriteSchema,
    LoginSchema,
    MoveStageSchema,
    OpportunitySchema,
    OpportunityWriteSchema,
    PipelineCreateSchema,
    PipelineSchema,
    ProductSchema,
    ProductWriteSchema,
    QuoteSchema,
    QuoteStatusSchema,
    QuoteWriteSchema,
    RegisterSchema,
    SessionSchema,
    StageCreateSchema,
    StageSchema,
    TenantSchema,
    UserCreateSchema,
    UserSchema,
)
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import create_access_token, verify_password
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
    QuoteModel,
    StageModel,
    TenantModel,
    UserModel,
)
from app.db.session import get_db
from app.services import crm

router = APIRouter()


def fail(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message)
    if isinstance(exc, UnauthorizedError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message)
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese dato ya existe en la empresa")
    raise exc


def session_for(user: UserModel, session: Session) -> SessionSchema:
    tenant = session.get(TenantModel, user.tenant_id)
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
    )
    return SessionSchema(
        access_token=token,
        user=UserSchema.model_validate(user),
        tenant=TenantSchema.model_validate(tenant),
    )


def save(session: Session, row):
    moment = crm.now()
    row.updated_at = moment
    if row.id is None and getattr(row, "created_at", None) is None:
        row.created_at = moment
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise fail(exc) from exc
    session.refresh(row)
    return row


def links_exist(session: Session, actor: UserModel, **links: int | None) -> None:
    models = {
        "account_id": AccountModel,
        "contact_id": ContactModel,
        "lead_id": LeadModel,
        "opportunity_id": OpportunityModel,
    }
    for key, record_id in links.items():
        if record_id is not None:
            crm.owned(session, models[key], record_id, actor.tenant_id)


@router.post("/auth/register", response_model=SessionSchema, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterSchema, session: Session = Depends(get_db)) -> SessionSchema:
    try:
        tenant, user = crm.create_company(
            session,
            company_name=payload.company_name,
            name=payload.name,
            email=payload.email,
            password=payload.password,
        )
    except (ConflictError, IntegrityError) as exc:
        raise fail(exc) from exc
    return session_for(user, session) if tenant else session_for(user, session)


@router.post("/auth/login", response_model=SessionSchema)
def login(payload: LoginSchema, session: Session = Depends(get_db)) -> SessionSchema:
    user = session.scalar(select(UserModel).where(UserModel.email == payload.email.lower().strip()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o contraseña incorrectos")
    tenant = session.get(TenantModel, user.tenant_id)
    if not user.is_active or tenant is None or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autorizado")
    return session_for(user, session)


@router.get("/auth/me", response_model=SessionSchema)
def me(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)) -> SessionSchema:
    return session_for(actor, session)


@router.get("/users", response_model=list[UserSchema])
def list_users(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)) -> list[UserModel]:
    return crm.list_owned(session, UserModel, actor.tenant_id)


@router.post("/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserModel:
    try:
        return crm.add_user(session, actor, **payload.model_dump())
    except (ConflictError, ForbiddenError, IntegrityError) as exc:
        raise fail(exc) from exc


@router.get("/accounts", response_model=list[AccountSchema])
def list_accounts(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    return crm.list_owned(session, AccountModel, actor.tenant_id)


@router.post("/accounts", response_model=AccountSchema, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
    except ForbiddenError as exc:
        raise fail(exc) from exc
    return save(session, AccountModel(tenant_id=actor.tenant_id, **payload.model_dump()))


@router.get("/accounts/{account_id}", response_model=AccountSchema)
def get_account(account_id: int, actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        return crm.owned(session, AccountModel, account_id, actor.tenant_id)
    except NotFoundError as exc:
        raise fail(exc) from exc


@router.patch("/accounts/{account_id}", response_model=AccountSchema)
def update_account(
    account_id: int,
    payload: AccountWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
        row = crm.owned(session, AccountModel, account_id, actor.tenant_id)
    except (ForbiddenError, NotFoundError) as exc:
        raise fail(exc) from exc
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    return save(session, row)


@router.get("/contacts", response_model=list[ContactSchema])
def list_contacts(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    return crm.list_owned(session, ContactModel, actor.tenant_id)


@router.post("/contacts", response_model=ContactSchema, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
        links_exist(session, actor, account_id=payload.account_id)
    except (ForbiddenError, NotFoundError) as exc:
        raise fail(exc) from exc
    return save(
        session,
        ContactModel(tenant_id=actor.tenant_id, owner_id=actor.id, **payload.model_dump()),
    )


@router.get("/leads", response_model=list[LeadSchema])
def list_leads(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    return crm.list_owned(session, LeadModel, actor.tenant_id)


@router.post("/leads", response_model=LeadSchema, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
        links_exist(session, actor, account_id=payload.account_id, contact_id=payload.contact_id)
    except (ForbiddenError, NotFoundError) as exc:
        raise fail(exc) from exc
    return save(session, LeadModel(tenant_id=actor.tenant_id, owner_id=actor.id, **payload.model_dump()))


@router.post("/leads/{lead_id}/convert", response_model=OpportunitySchema, status_code=status.HTTP_201_CREATED)
def convert_lead(lead_id: int, actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        return crm.convert_lead(session, actor, lead_id)
    except (NotFoundError, ConflictError, ForbiddenError) as exc:
        raise fail(exc) from exc


@router.get("/pipelines", response_model=list[PipelineSchema])
def list_pipelines(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    stmt = (
        select(PipelineModel)
        .where(PipelineModel.tenant_id == actor.tenant_id)
        .options(selectinload(PipelineModel.stages))
        .order_by(PipelineModel.id.asc())
    )
    pipelines = list(session.scalars(stmt).unique().all())
    for pipeline in pipelines:
        pipeline.stages.sort(key=lambda stage: stage.position)
    return pipelines


@router.post("/pipelines", response_model=PipelineSchema, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    payload: PipelineCreateSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_admin(actor)
    except ForbiddenError as exc:
        raise fail(exc) from exc
    moment = crm.now()
    pipeline = PipelineModel(
        tenant_id=actor.tenant_id,
        name=payload.name.strip(),
        is_default=False,
        created_at=moment,
        updated_at=moment,
    )
    try:
        session.add(pipeline)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise fail(exc) from exc
    session.refresh(pipeline)
    return pipeline


@router.post("/pipelines/{pipeline_id}/stages", response_model=StageSchema, status_code=status.HTTP_201_CREATED)
def create_stage(
    pipeline_id: int,
    payload: StageCreateSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return crm.add_stage(session, actor, pipeline_id, **payload.model_dump())
    except (NotFoundError, ForbiddenError, IntegrityError) as exc:
        raise fail(exc) from exc


@router.get("/opportunities", response_model=list[OpportunitySchema])
def list_opportunities(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    return crm.list_owned(session, OpportunityModel, actor.tenant_id)


@router.post("/opportunities", response_model=OpportunitySchema, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return crm.create_opportunity(session, actor, **payload.model_dump())
    except (NotFoundError, ConflictError, ForbiddenError) as exc:
        raise fail(exc) from exc


@router.post("/opportunities/{opportunity_id}/stage", response_model=OpportunitySchema)
def move_opportunity(
    opportunity_id: int,
    payload: MoveStageSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return crm.move_opportunity(session, actor, opportunity_id, payload.stage_id)
    except (NotFoundError, ConflictError, ForbiddenError) as exc:
        raise fail(exc) from exc


@router.get("/activities", response_model=list[ActivitySchema])
def list_activities(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    return crm.list_owned(session, ActivityModel, actor.tenant_id)


@router.post("/activities", response_model=ActivitySchema, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: ActivityWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
        links_exist(
            session,
            actor,
            account_id=payload.account_id,
            contact_id=payload.contact_id,
            lead_id=payload.lead_id,
            opportunity_id=payload.opportunity_id,
        )
    except (ForbiddenError, NotFoundError) as exc:
        raise fail(exc) from exc
    return save(session, ActivityModel(tenant_id=actor.tenant_id, owner_id=actor.id, **payload.model_dump()))


@router.post("/activities/{activity_id}/complete", response_model=ActivitySchema)
def complete_activity(
    activity_id: int,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
        row = crm.owned(session, ActivityModel, activity_id, actor.tenant_id)
    except (ForbiddenError, NotFoundError) as exc:
        raise fail(exc) from exc
    row.completed_at = crm.now()
    return save(session, row)


@router.get("/products", response_model=list[ProductSchema])
def list_products(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    return crm.list_owned(session, ProductModel, actor.tenant_id)


@router.post("/products", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
    except ForbiddenError as exc:
        raise fail(exc) from exc
    data = payload.model_dump()
    if data["code"] is not None:
        data["code"] = data["code"].strip() or None
    return save(session, ProductModel(tenant_id=actor.tenant_id, is_active=True, **data))


@router.get("/quotes", response_model=list[QuoteSchema])
def list_quotes(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    stmt = (
        select(QuoteModel)
        .where(QuoteModel.tenant_id == actor.tenant_id)
        .options(selectinload(QuoteModel.items))
        .order_by(QuoteModel.id.desc())
    )
    return list(session.scalars(stmt).unique().all())


@router.post("/quotes", response_model=QuoteSchema, status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuoteWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        quote = crm.create_quote(session, actor, payload.model_dump())
    except (NotFoundError, ConflictError, ForbiddenError) as exc:
        raise fail(exc) from exc
    session.refresh(quote)
    return quote


@router.patch("/quotes/{quote_id}/status", response_model=QuoteSchema)
def update_quote_status(
    quote_id: int,
    payload: QuoteStatusSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
        quote = crm.owned(session, QuoteModel, quote_id, actor.tenant_id)
    except (ForbiddenError, NotFoundError) as exc:
        raise fail(exc) from exc
    quote.status = payload.status
    save(session, quote)
    return quote


@router.get("/custom-fields", response_model=list[CustomFieldSchema])
def list_custom_fields(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)):
    return crm.list_owned(session, CustomFieldModel, actor.tenant_id)


@router.post("/custom-fields", response_model=CustomFieldSchema, status_code=status.HTTP_201_CREATED)
def create_custom_field(
    payload: CustomFieldWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_admin(actor)
    except ForbiddenError as exc:
        raise fail(exc) from exc
    if payload.field_type == "select" and not payload.options:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Un campo de lista necesita opciones")
    return save(session, CustomFieldModel(tenant_id=actor.tenant_id, is_active=True, **payload.model_dump()))


@router.put("/custom-values", response_model=CustomValueSchema)
def set_custom_value(
    payload: CustomValueWriteSchema,
    actor: UserModel = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        crm.require_write(actor)
        field = crm.owned(session, CustomFieldModel, payload.field_id, actor.tenant_id)
    except (ForbiddenError, NotFoundError) as exc:
        raise fail(exc) from exc
    existing = session.scalar(
        select(CustomFieldValueModel).where(
            CustomFieldValueModel.tenant_id == actor.tenant_id,
            CustomFieldValueModel.field_id == field.id,
            CustomFieldValueModel.record_id == payload.record_id,
        )
    )
    if existing is None:
        existing = CustomFieldValueModel(
            tenant_id=actor.tenant_id,
            field_id=field.id,
            record_id=payload.record_id,
            value=payload.value,
        )
    else:
        existing.value = payload.value
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


@router.get("/dashboard", response_model=DashboardSchema)
def dashboard(actor: UserModel = Depends(get_current_user), session: Session = Depends(get_db)) -> dict:
    return crm.dashboard(session, actor.tenant_id)
