from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RoleName = Literal["owner", "admin", "sales", "viewer"]
LeadStatus = Literal["new", "contacted", "qualified", "unqualified", "converted"]
ActivityKind = Literal["task", "call", "meeting"]
StageOutcome = Literal["open", "won", "lost"]
QuoteStatus = Literal["draft", "sent", "accepted", "rejected", "expired"]
EntityType = Literal["account", "contact", "lead", "opportunity"]
FieldType = Literal["text", "number", "date", "boolean", "select"]


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterSchema(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "sales", "viewer"]


class UserSchema(OrmSchema):
    id: int
    tenant_id: int
    name: str
    email: EmailStr
    role: str
    is_active: bool


class TenantSchema(OrmSchema):
    id: int
    name: str
    slug: str


class SessionSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSchema
    tenant: TenantSchema


class AccountWriteSchema(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    industry: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=240)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=4000)


class AccountSchema(AccountWriteSchema, OrmSchema):
    id: int
    tenant_id: int


class ContactWriteSchema(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    account_id: int | None = None


class ContactSchema(ContactWriteSchema, OrmSchema):
    id: int
    tenant_id: int
    owner_id: int | None


class LeadWriteSchema(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    source: str | None = Field(default=None, max_length=80)
    status: LeadStatus = "new"
    notes: str | None = Field(default=None, max_length=4000)
    account_id: int | None = None
    contact_id: int | None = None


class LeadSchema(LeadWriteSchema, OrmSchema):
    id: int
    tenant_id: int
    owner_id: int | None


class StageSchema(OrmSchema):
    id: int
    pipeline_id: int
    name: str
    position: int
    probability: int
    outcome: str


class StageCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    probability: int = Field(ge=0, le=100)
    outcome: StageOutcome = "open"


class PipelineCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PipelineSchema(OrmSchema):
    id: int
    name: str
    is_default: bool
    stages: list[StageSchema] = []


class OpportunityWriteSchema(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    pipeline_id: int | None = None
    stage_id: int | None = None
    account_id: int | None = None
    contact_id: int | None = None
    lead_id: int | None = None
    expected_close_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class OpportunitySchema(OrmSchema):
    id: int
    tenant_id: int
    pipeline_id: int
    stage_id: int
    account_id: int | None
    contact_id: int | None
    lead_id: int | None
    owner_id: int | None
    title: str
    amount: Decimal
    currency: str
    expected_close_date: date | None
    status: str
    notes: str | None


class MoveStageSchema(BaseModel):
    stage_id: int


class ActivityWriteSchema(BaseModel):
    kind: ActivityKind
    subject: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    account_id: int | None = None
    contact_id: int | None = None
    lead_id: int | None = None
    opportunity_id: int | None = None


class ActivitySchema(ActivityWriteSchema, OrmSchema):
    id: int
    tenant_id: int
    owner_id: int | None
    completed_at: datetime | None


class ProductWriteSchema(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    unit_price: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    is_service: bool = False


class ProductSchema(ProductWriteSchema, OrmSchema):
    id: int
    tenant_id: int
    is_active: bool


class QuoteItemWriteSchema(BaseModel):
    product_id: int | None = None
    description: str | None = Field(default=None, max_length=180)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)


class QuoteItemSchema(OrmSchema):
    id: int
    product_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    line_total: Decimal


class QuoteWriteSchema(BaseModel):
    account_id: int
    opportunity_id: int | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    valid_until: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    items: list[QuoteItemWriteSchema] = Field(min_length=1)


class QuoteSchema(OrmSchema):
    id: int
    tenant_id: int
    account_id: int
    opportunity_id: int | None
    number: str
    status: str
    currency: str
    valid_until: date | None
    notes: str | None
    subtotal: Decimal
    total: Decimal
    items: list[QuoteItemSchema] = []


class QuoteStatusSchema(BaseModel):
    status: QuoteStatus


class CustomFieldWriteSchema(BaseModel):
    entity_type: EntityType
    label: str = Field(min_length=1, max_length=80)
    key: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    field_type: FieldType
    options: list[str] | None = None
    required: bool = False


class CustomFieldSchema(CustomFieldWriteSchema, OrmSchema):
    id: int
    tenant_id: int
    is_active: bool


class CustomValueWriteSchema(BaseModel):
    field_id: int
    record_id: int
    value: str | None = Field(default=None, max_length=2000)


class CustomValueSchema(OrmSchema):
    id: int
    field_id: int
    record_id: int
    value: str | None


class DashboardSchema(BaseModel):
    accounts: int
    contacts: int
    open_leads: int
    open_opportunities: int
    pipeline_amount: Decimal
    open_activities: int
    open_quotes: int
