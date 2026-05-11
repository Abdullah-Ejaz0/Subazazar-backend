-- ────────────────────────────────────────────────────────────
--  F17. farmer_complete_signup(p_phone, p_full_name, p_language, p_voice)
--       Called after OTP verification on the frontend.
--       Finds the profile row (auto-created by on_auth_user_created trigger)
--       and updates it with the farmer's preferences.
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.farmer_complete_signup(
    p_phone     text,
    p_full_name text DEFAULT NULL,
    p_language  public.app_language DEFAULT 'en',
    p_voice     boolean DEFAULT false
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_user_id uuid;
BEGIN
    -- Find the profile created by the trigger
    SELECT id INTO v_user_id
    FROM public.profiles
    WHERE phone = p_phone;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'No profile found for phone %. Auth user may not have been created yet.', p_phone;
    END IF;

    -- Update profile with farmer preferences
    UPDATE public.profiles
    SET full_name           = COALESCE(p_full_name, full_name),
        role                = 'farmer',
        language            = p_language,
        voice_assistance    = p_voice,
        onboarding_complete = true
    WHERE id = v_user_id;

    -- Create/update user_settings row
    PERFORM public.update_user_settings(v_user_id, p_language, p_voice);
END;
$$;

COMMENT ON FUNCTION public.farmer_complete_signup IS
  'Called after OTP verification. Updates the auto-created profile with farmer preferences and marks onboarding complete.';


-- ────────────────────────────────────────────────────────────
--  F18. update_user_profile(p_user_id, p_full_name, p_avatar_url, 
--                           p_region, p_username, p_language, p_voice)
--       General-purpose profile update function.
--       Only updates fields that are not null (partial update).
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.update_user_profile(
    p_user_id    uuid,
    p_full_name  text DEFAULT NULL,
    p_avatar_url text DEFAULT NULL,
    p_region     text DEFAULT NULL,
    p_username   text DEFAULT NULL,
    p_language   public.app_language DEFAULT NULL,
    p_voice      boolean DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    UPDATE public.profiles
    SET full_name        = COALESCE(p_full_name, full_name),
        avatar_url       = COALESCE(p_avatar_url, avatar_url),
        region           = COALESCE(p_region, region),
        username         = COALESCE(p_username, username),
        language         = COALESCE(p_language, language),
        voice_assistance = COALESCE(p_voice, voice_assistance)
    WHERE id = p_user_id;

    -- Sync settings table if language or voice changed
    IF p_language IS NOT NULL OR p_voice IS NOT NULL THEN
        PERFORM public.update_user_settings(
            p_user_id,
            COALESCE(p_language, (SELECT language FROM public.profiles WHERE id = p_user_id)),
            COALESCE(p_voice,    (SELECT voice_assistance FROM public.profiles WHERE id = p_user_id))
        );
    END IF;
END;
$$;

COMMENT ON FUNCTION public.update_user_profile IS
  'Partial profile update — only updates non-null parameters. Keeps profiles and user_settings in sync.';


-- ────────────────────────────────────────────────────────────
--  F19. check_farmer_phone(p_phone)
--       Returns 1 if farmer exists, 0 if not.
--       Also returns profile data if the farmer exists.
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.check_farmer_phone(p_phone text)
RETURNS TABLE (
    user_exists  int,
    user_id      uuid,
    full_name    text,
    phone        text,
    language     public.app_language,
    voice_assistance boolean,
    onboarding_complete boolean
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT
        1 AS user_exists,
        p.id AS user_id,
        p.full_name,
        p.phone,
        p.language,
        p.voice_assistance,
        p.onboarding_complete
    FROM public.profiles p
    WHERE p.phone = p_phone AND p.role = 'farmer'
    LIMIT 1;
$$;

COMMENT ON FUNCTION public.check_farmer_phone IS
  'Returns profile data if a farmer with the given phone exists, empty result set otherwise.';


-- ────────────────────────────────────────────────────────────
--  F20. cleanup_expired_sessions()
--       Utility function to clean up stale/expired data.
--       Can be called via pg_cron or a scheduled edge function.
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.cleanup_expired_sessions()
RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_deleted int;
BEGIN
    -- Clean up any profiles that never completed onboarding
    -- and are older than 7 days (abandoned signups)
    DELETE FROM public.profiles
    WHERE onboarding_complete = false
      AND created_at < now() - interval '7 days'
      AND role = 'farmer';

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

COMMENT ON FUNCTION public.cleanup_expired_sessions IS
  'Removes abandoned farmer signups (onboarding incomplete, older than 7 days). Schedule via pg_cron.';


-- ────────────────────────────────────────────────────────────
--  Additional RLS policy: Allow service role to insert profiles
--  (needed when creating expert accounts via admin API)
-- ────────────────────────────────────────────────────────────

-- Allow users to read other users' basic info (for community posts author names)
DO $$
BEGIN
    -- Only create if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'profiles' AND policyname = 'Anyone authenticated can read basic profiles'
    ) THEN
        CREATE POLICY "Anyone authenticated can read basic profiles"
            ON public.profiles FOR SELECT
            USING (auth.role() = 'authenticated');
    END IF;
END
$$;

