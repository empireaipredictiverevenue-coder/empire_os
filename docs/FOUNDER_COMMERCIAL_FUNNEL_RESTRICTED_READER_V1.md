# Founder Commercial Funnel Restricted Reader V1

## Diagram

```text
canonical EmpireDB tables
(prospect acquisition -> buyer review -> outbound -> replies -> closer/terms
 -> payment evidence -> fulfilment -> commercial outcome/revenue event)
                              |
                              v
          get_founder_commercial_funnel()
                              |
          restricted materializer capability
                              |
                              v
        runtime/commercial_funnel/latest.json
                              |
                              v
                 Founder Console / read APIs
```

## Authority contract

The RPC is a bounded read-only projection. It grants no INSERT, UPDATE, DELETE,
send, call, terms, payment, fulfilment, revenue-recognition or accounting
authority. It must be SECURITY DEFINER owned by the non-login
`empiredb_migrator`, with empty search_path. EXECUTE is revoked from PUBLIC,
`empiredb_app`, and the materializer login role, and granted only to the
non-login `empire_intelligence_materializer` capability role.

The materializer must receive no direct table privileges. Counts and money are
derived only from canonical EmpireDB relations. Recognized revenue and realized
margin come only from canonical `commercial_events` rows whose event type is
`revenue_recognized`; missing real events therefore remain zero/false rather
than being inferred from expected economics.

The projection must preserve existing Founder Console schema:
`counts`, outbound/reply count maps, `recognized_revenue_cents`,
`realized_margin_cents`, `actual_revenue`, and `execution_authority=none`.
No synthetic rows and no fallback to legacy SQLite/JSONL are permitted.

Migration 027 is held for explicit database activation after executable
security/semantics tests pass.
