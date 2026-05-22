-- Allow vendor role on signup and auto-link profile to vendors row by email

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role TEXT;
  v_name TEXT;
  v_vendor_id UUID;
BEGIN
  v_name := COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1));
  v_role := COALESCE(NEW.raw_user_meta_data->>'role', 'tenant');

  IF v_role NOT IN ('admin', 'manager', 'inspector', 'tenant', 'vendor') THEN
    v_role := 'tenant';
  END IF;

  v_vendor_id := NULL;
  IF v_role = 'vendor' AND NEW.email IS NOT NULL THEN
    SELECT id INTO v_vendor_id FROM public.vendors
    WHERE lower(email) = lower(NEW.email)
    LIMIT 1;
  END IF;

  INSERT INTO public.profiles (id, full_name, role, vendor_id)
  VALUES (NEW.id, v_name, v_role, v_vendor_id)
  ON CONFLICT (id) DO UPDATE
    SET
      full_name = COALESCE(EXCLUDED.full_name, profiles.full_name),
      role = COALESCE(EXCLUDED.role, profiles.role),
      vendor_id = COALESCE(EXCLUDED.vendor_id, profiles.vendor_id),
      updated_at = NOW();

  RETURN NEW;
END;
$$;
