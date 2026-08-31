CREATE OR REPLACE FUNCTION embedding_from_query(q TEXT) RETURNS vector(384) AS $$
DECLARE
  v vector(384);
  h bigint := abs(hashtext(q));
  i int;
  arr float[] := '{}';
BEGIN
  FOR i IN 1..384 LOOP
    h := (h * 1103515245 + 12345) % 2147483647;
    arr := arr || ((h % 1000)::float / 1000.0);
  END LOOP;
  v := arr::vector(384);
  RETURN v;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
