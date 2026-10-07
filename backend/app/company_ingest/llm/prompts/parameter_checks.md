# Parameter Checks Prompt — Stage 4c

## Purpose

The `propose_checks` stage asks the LLM to generate SQL checks for a compliance dataset.
Each check is a SELECT statement that returns rows **violating** or **newly in scope** for a
regulatory parameter.

## System Prompt

```
You are proposing SQL checks for a compliance dataset.

Each check is a SELECT statement that returns rows VIOLATING or NEWLY IN SCOPE for a regulatory parameter.
Rules:
- Use only column names from the provided schema
- Use {placeholder} syntax for parameter values; each placeholder must bind to a provided parameter_pk
- Write single SELECT or WITH...SELECT statements only; no semicolons, no DDL
- 0 to 5 checks per dataset
- Each check's purpose must be a complete sentence explaining what it validates
```

## User Message Structure

```
Dataset: <name>
Row count: <n>
Columns:
  - <col> (<dtype>): null_rate=<r>, distinct=<d>[, top_values=[...]]

Describing clauses:
  clause_id: <id>
  text: <first 300 chars>
    param_pk=<pk>: <ParameterEntry>

Placeholder rules:
- Use {placeholder_name} syntax in sql_template
- Each placeholder must bind to a parameter_pk from the clauses above
- Only use column names listed in Columns above
```

## Response Schema (`DatasetEnrichment`)

```json
{
  "description": "string — one or two sentences describing the dataset",
  "columns": [
    {
      "column_name": "string",
      "semantic_role": "string or null",
      "description": "string or null"
    }
  ],
  "checks": [
    {
      "purpose": "string — complete sentence describing what the check validates",
      "sql_template": "string — SELECT ... WHERE col > {placeholder}",
      "param_bindings": [
        {
          "placeholder": "string — the {placeholder} name used in sql_template",
          "parameter_pk": "string — clause_id:index from describing clauses"
        }
      ]
    }
  ]
}
```

## Validation Rules (post-LLM)

1. Each `placeholder` in `param_bindings` must appear as `{placeholder}` in `sql_template`. Invalid bindings are dropped and a `check_binding_invalid` issue is issued.
2. Each `parameter_pk` must exist in the parameter map built from describing clauses. Invalid bindings are dropped and a `check_binding_invalid` issue is issued.
3. At most 5 checks are kept (enforced by `DatasetEnrichment.cap_checks`).
4. Each stored proposal increments `ctx.stats["checks_proposed"]`.
