-- Remove old request policies
DROP POLICY IF EXISTS "requests_select" ON public.requests;
DROP POLICY IF EXISTS "requests_insert" ON public.requests;
DROP POLICY IF EXISTS "requests_update" ON public.requests;
DROP POLICY IF EXISTS "requests_delete" ON public.requests;


-- SELECT
CREATE POLICY "requests_select"
ON public.requests
FOR SELECT
TO authenticated
USING (
  (select auth.uid()) = sender_id
  OR
  (select auth.uid()) = reciever_id
);


-- INSERT
CREATE POLICY "requests_insert"
ON public.requests
FOR INSERT
TO authenticated
WITH CHECK (
  (select auth.uid()) = sender_id
);


-- UPDATE
CREATE POLICY "requests_update"
ON public.requests
FOR UPDATE
TO authenticated
USING (
  (select auth.uid()) = sender_id
  OR
  (select auth.uid()) = reciever_id
)
WITH CHECK (
  (select auth.uid()) = sender_id
  OR
  (select auth.uid()) = reciever_id
);


-- DELETE
CREATE POLICY "requests_delete"
ON public.requests
FOR DELETE
TO authenticated
USING (
  (select auth.uid()) = sender_id
  OR
  (select auth.uid()) = reciever_id
);
