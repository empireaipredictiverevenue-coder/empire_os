-- Narrow first-touch personhood read for the dedicated outbound approver.
-- Generic empiredb_app receives no additional authority.
-- No payment/revenue/send authority added here.

SET ROLE empiredb_migrator;

GRANT SELECT (id, business_name)
ON public.prospects
TO empire_outbound_approver;

DROP POLICY IF EXISTS
  prospects_outbound_approver_personhood_select
ON public.prospects;

CREATE POLICY
  prospects_outbound_approver_personhood_select
ON public.prospects
FOR SELECT
TO empire_outbound_approver
USING (true);

RESET ROLE;
