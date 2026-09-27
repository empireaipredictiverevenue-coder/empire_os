-- Canonical enterprise buyer candidate review authority.
-- Captured from the live canonical database after founder-approved enterprise review repair.
-- PostgreSQL default SECURITY INVOKER is intentional; do not change this function to SECURITY DEFINER.
-- This function approves internal review only. It does not grant live send, binding terms,
-- payment movement, or revenue-recognition authority.

CREATE OR REPLACE FUNCTION public.auto_review_enterprise_buyer_candidate(p_review_id uuid, p_daily_cap integer DEFAULT 10)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
    declare
      r public.buyer_candidate_reviews%rowtype;
      contact jsonb;
      approved_today integer;
      allowed_products text[] := array[
        'predictive_revenue_diagnostic',
        'predictive_revenue_intelligence_os',
        'predictive_revenue_command_center',
        'predictive_revenue_autonomous_os',
        'predictive_revenue_private_strategic'
      ];
    begin
      if p_daily_cap is null or p_daily_cap < 1 or p_daily_cap > 25 then
        raise exception 'enterprise daily review cap must be 1-25';
      end if;

      select * into r
        from public.buyer_candidate_reviews
       where id=p_review_id
       for update;

      if not found then
        raise exception 'buyer candidate review not found';
      end if;

      if r.status='approved' then
        return jsonb_build_object(
          'decision','existing',
          'review_id',r.id,
          'status',r.status,
          'enterprise',true,
          'actual_revenue',false
        );
      end if;

      if r.status<>'pending' then
        raise exception 'pending buyer candidate review required';
      end if;

      if r.proposed_at < clock_timestamp()-interval '14 days' then
        raise exception 'enterprise buyer candidate review expired';
      end if;

      if not (r.offer_key = any(allowed_products)) then
        raise exception 'offer outside enterprise review authority';
      end if;

      if coalesce(r.evidence->>'niche','') <> 'predictive_revenue_enterprise' then
        raise exception 'enterprise niche evidence required';
      end if;

      if coalesce(r.evidence->>'wave','') not in ('direct_enterprise','sponsor_enterprise') then
        raise exception 'enterprise wave evidence required';
      end if;

      if coalesce(lower(r.evidence->>'review_ready'),'false') <> 'true'
         or coalesce(lower(r.evidence->>'outreach_ready'),'false') <> 'true' then
        raise exception 'review and outreach readiness required';
      end if;

      if coalesce(lower(r.evidence->>'enterprise_fit_revalidated'),'false') <> 'true'
         or coalesce(lower(r.evidence->>'contact_personhood_valid'),'false') <> 'true'
         or coalesce(lower(r.evidence->>'has_named_contact'),'false') <> 'true' then
        raise exception 'current enterprise fit and person evidence required';
      end if;

      if coalesce(r.company_score,0) < 50
         or coalesce(r.decision_score,0) < 0.80 then
        raise exception 'candidate score below enterprise review threshold';
      end if;

      if coalesce(r.evidence->>'contact_source','') not in
         ('official_site','official_site_current','public_record','press_release') then
        raise exception 'contact source outside enterprise review authority';
      end if;

      if not (
        r.evidence->'target_product_codes' @> jsonb_build_array(r.offer_key)
      ) then
        raise exception 'offer not bound to enterprise target product evidence';
      end if;

      select item into contact
        from jsonb_array_elements(
          case
            when jsonb_typeof(r.evidence->'verified_contacts')='array'
            then r.evidence->'verified_contacts'
            else '[]'::jsonb
          end
        ) items(item)
       where lower(trim(coalesce(item->>'email',''))) =
             lower(trim(coalesce(r.contact_email,'')))
       limit 1;

      if contact is null then
        raise exception 'verified contact evidence required';
      end if;

      if contact->'bound_to_decision_maker' is distinct from 'true'::jsonb
         or contact->'has_mx' is distinct from 'true'::jsonb
         or contact->'is_valid' is distinct from 'true'::jsonb
         or contact->'is_disposable' is distinct from 'false'::jsonb
         or contact->'is_role_address' is distinct from 'false'::jsonb then
        raise exception 'verified enterprise decision-maker contact required';
      end if;

      if jsonb_typeof(contact->'confidence') <> 'number'
         or (contact->>'confidence')::numeric < 0.70 then
        raise exception 'contact confidence below enterprise threshold';
      end if;

      if coalesce(contact->>'source','') not in
         ('official_site','official_site_current','public_record','press_release') then
        raise exception 'verified contact source outside enterprise authority';
      end if;

      if exists (
        select 1
          from public.outbound_suppressions s
         where s.normalized_contact=lower(trim(r.contact_email))
      ) then
        raise exception 'recipient is suppressed';
      end if;

      if exists (
        select 1
          from public.outbound_intents i
         where i.normalized_recipient=lower(trim(r.contact_email))
           and i.status in (
             'sending','sent','delivered','replied',
             'bounced','failed','suppressed'
           )
      ) then
        raise exception 'existing outbound history requires explicit review';
      end if;

      select count(*)::integer into approved_today
        from public.buyer_candidate_review_events e
       where e.event_type='approved'
         and e.actor='enterprise-standing-authority'
         and e.occurred_at >= date_trunc('day',clock_timestamp());

      if approved_today >= p_daily_cap then
        raise exception 'enterprise daily candidate cap reached';
      end if;

      update public.buyer_candidate_reviews
         set status='approved',
             reviewed_at=clock_timestamp(),
             reviewed_by='enterprise-standing-authority',
             review_note='Approved under evidence-gated enterprise review authority. Live outbound remains separately governed.'
       where id=r.id
       returning * into r;

      insert into public.buyer_candidate_review_events(
        review_id,event_type,actor,payload
      )
      values(
        r.id,'approved','enterprise-standing-authority',
        jsonb_build_object(
          'enterprise_authority',true,
          'enterprise_fit_revalidated',true,
          'contact_personhood_valid',true,
          'daily_cap',p_daily_cap,
          'live_outbound_send',false,
          'binding_terms',false,
          'payment_action',false,
          'actual_revenue',false
        )
      );

      return jsonb_build_object(
        'decision','approved',
        'review_id',r.id,
        'status',r.status,
        'enterprise_authority',true,
        'live_outbound_send',false,
        'actual_revenue',false
      );
    end;
    $function$;

revoke execute on function public.auto_review_enterprise_buyer_candidate(uuid, integer)
  from public, anon, authenticated;

grant execute on function public.auto_review_enterprise_buyer_candidate(uuid, integer)
  to service_role;
