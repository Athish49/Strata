from enum import StrEnum


class Profile(StrEnum):
    P1_PROSE = "p1_prose"
    P2_REGISTER = "p2_register"
    P3_DATASET = "p3_dataset"
    P4_REFERENCE = "p4_reference"
    RENDER = "render"


class DocClass(StrEnum):
    PROCEDURE = "procedure"
    PLAN = "plan"
    TARIFF = "tariff"
    REGISTER = "register"
    CALENDAR = "calendar"
    RETENTION_SCHEDULE = "retention_schedule"
    REFERENCE = "reference"


class UnitKind(StrEnum):
    SECTION = "section"
    APPENDIX = "appendix"
    FORM_FIELD = "form_field"
    TABLE_ROW = "table_row"
    TARIFF_SUBRULE = "tariff_subrule"
    REGISTER_ROW = "register_row"
    OTHER = "other"


class SectionKind(StrEnum):
    PURPOSE = "purpose"
    SCOPE = "scope"
    DEFINITIONS = "definitions"
    REGULATORY_BASIS = "regulatory_basis"
    ROLES = "roles"
    PROCEDURE = "procedure"
    RECORDS = "records"
    TRAINING = "training"
    RELATED_DOCS = "related_docs"
    REVISION_HISTORY = "revision_history"
    APPROVAL = "approval"
    APPENDIX = "appendix"
    FRONT_MATTER = "front_matter"
    OTHER = "other"


class ClauseRole(StrEnum):
    INTERNAL_TARGET = "internal_target"
    COMPANY_POSITION = "company_position"
    TEMPLATE_FIELD = "template_field"
    DEFINITION = "definition"
    BOILERPLATE = "boilerplate"
    REGULATORY_RESTATEMENT = "regulatory_restatement"
    OUT_OF_SCOPE_REFERENCE = "out_of_scope_reference"
    INTERNAL_PROCEDURE = "internal_procedure"
    INFORMATIONAL = "informational"


class ParameterKind(StrEnum):
    NUMBER = "number"
    PERIOD = "period"
    DEADLINE = "deadline"
    FREQUENCY = "frequency"
    THRESHOLD = "threshold"
    AMOUNT = "amount"
    QUALIFIER = "qualifier"
    CONDITION = "condition"
    EXCEPTION = "exception"
    PARTY = "party"
    CHANNEL = "channel"
    CONTENT_ELEMENT = "content_element"
    APPLICABILITY = "applicability"
    RECORD_RETENTION = "record_retention"


class Qualifier(StrEnum):
    WITHIN = "within"
    AT_LEAST = "at_least"
    NOT_MORE_THAN = "not_more_than"
    NOT_LESS_THAN = "not_less_than"
    PRIOR_TO = "prior_to"
    AFTER = "after"
    EXACTLY = "exactly"


class DayType(StrEnum):
    CALENDAR = "calendar"
    BUSINESS = "business"
    WORKING = "working"
    HOURS = "hours"
    N_A = "n_a"


class LinkType(StrEnum):
    REFERENCES_DOC = "references_doc"
    REFERENCES_CLAUSE = "references_clause"
    REFERENCES_TARIFF = "references_tariff"
    REFERENCES_FORM = "references_form"
    REFERENCES_RECORD_SERIES = "references_record_series"
    REFERENCES_OBLIGATION = "references_obligation"
    RESTATES = "restates"


class ColumnRole(StrEnum):
    ID = "id"
    CITATION = "citation"
    REGULATORY_VALUE = "regulatory_value"
    RULE_QUOTE = "rule_quote"
    SUMMARY_TEXT = "summary_text"
    REFERENCE_LIST = "reference_list"
    OWNER_PERSON = "owner_person"
    DATE = "date"
    ENUM = "enum"
    STATUS = "status"
    FREE_TEXT = "free_text"
    IGNORE = "ignore"


class SemanticRole(StrEnum):
    ID = "id"
    FOREIGN_KEY = "foreign_key"
    TIMESTAMP = "timestamp"
    DURATION = "duration"
    QUANTITY = "quantity"
    FLAG = "flag"
    CATEGORY = "category"
    CLAUSE_REF = "clause_ref"
    FREE_TEXT = "free_text"
