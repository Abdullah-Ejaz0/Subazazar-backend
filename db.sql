--  0. EXTENSIONS
create extension if not exists "uuid-ossp";

--  1. REFERENCE / LOOKUP TABLES
--     These are seeded once and rarely change.

-- 1a. Crops supported by the AI model
create table public.crops (
    id          uuid primary key default uuid_generate_v4(),
    name        text not null unique,          -- e.g. 'Wheat', 'Rice', 'Maize'
    name_ur     text,                          -- Urdu label
    name_pa     text,                          -- Punjabi label
    icon_url    text,                          -- optional crop icon
    created_at  timestamptz not null default now()
);
comment on table public.crops is 'Supported crop types for disease detection.';


-- 1b. Diseases — one row per known disease
create table public.diseases (
    id              uuid primary key default uuid_generate_v4(),
    crop_id         uuid not null references public.crops(id) on delete restrict,
    name            text not null,             -- e.g. 'Leaf Blight'
    name_ur         text,
    name_pa         text,
    causes          text,                      -- "Fungus due to high humidity"
    symptoms        text,                      -- "Brown spots on leaves, yellow edges"
    prevention      text,                      -- "Ensure good airflow..."
    risk_default    text check (risk_default in ('low','medium','high')) default 'medium',
    created_at      timestamptz not null default now(),
    unique (crop_id, name)
);
comment on table public.diseases is 'Disease catalogue per crop, including educational content shown on the Details screen.';


-- 1c. Treatments — one or more chemical treatments per disease
create table public.treatments (
    id              uuid primary key default uuid_generate_v4(),
    disease_id      uuid not null references public.diseases(id) on delete cascade,
    chemical_name   text not null,             -- 'Copper Oxychloride'
    chemical_ur     text,
    chemical_pa     text,
    dosage          text not null,             -- '2g per liter water'
    frequency       text not null,             -- 'Every 5 days'
    disclaimer      text default 'Always consult your local agricultural officer before use.',
    created_at      timestamptz not null default now()
);
comment on table public.treatments is 'Rule-based treatment recommendations per disease.';


-- 1d. Chatbot FAQs (seeded static content)
create table public.chatbot_faqs (
    id          uuid primary key default uuid_generate_v4(),
    category    text not null,                 -- 'How to scan', 'Disease info', 'Pesticide', 'Weather'
    question    text not null,
    question_ur text,
    question_pa text,
    answer      text not null,
    answer_ur   text,
    answer_pa   text,
    sort_order  int not null default 0,
    created_at  timestamptz not null default now()
);
comment on table public.chatbot_faqs is 'Static FAQ content for the offline-capable chatbot.';

--  2. USER PROFILE
--     Extends Supabase auth.users (one-to-one via id).

create type public.user_role as enum ('farmer', 'expert');
create type public.app_language as enum ('en', 'ur', 'pa');

create table public.profiles (
    id                  uuid primary key references auth.users(id) on delete cascade,
    full_name           text,
    username            text unique,           -- optional username (required for experts)
    phone               text unique,           -- farmer primary identifier
    avatar_url          text,
    role                public.user_role not null default 'farmer',
    language            public.app_language not null default 'en',
    voice_assistance    boolean not null default false,
    region              text,                  -- free-text region / district (used for broadcast targeting)
    is_verified_expert  boolean not null default false,   -- admin-verified flag for experts
    onboarding_complete boolean not null default false,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
comment on table public.profiles is
  'App-level user profile extending auth.users. Farmers use phone auth; experts use email/password.';

-- Keep updated_at current automatically
create or replace function public.handle_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger trg_profiles_updated_at
    before update on public.profiles
    for each row execute function public.handle_updated_at();

-- Auto-create a profile row whenever a new auth user is created
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    insert into public.profiles (id, phone, full_name)
    values (
        new.id,
        new.phone,
        coalesce(new.raw_user_meta_data->>'full_name', null)
    );
    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

--  3. USER SETTINGS
--     Kept separate so profiles stays lightweight.

create table public.user_settings (
    id                  uuid primary key default uuid_generate_v4(),
    user_id             uuid not null unique references public.profiles(id) on delete cascade,
    language            public.app_language not null default 'en',
    voice_guidance      boolean not null default false,
    offline_content_kb  int not null default 0,    -- bytes downloaded for offline use
    updated_at          timestamptz not null default now()
);
comment on table public.user_settings is 'Per-user app settings (language, voice, offline cache size).';

create trigger trg_user_settings_updated_at
    before update on public.user_settings
    for each row execute function public.handle_updated_at();


--  4. SCAN HISTORY
create type public.risk_level as enum ('low', 'medium', 'high');

create table public.scans (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references public.profiles(id) on delete cascade,
    crop_id         uuid references public.crops(id) on delete set null,
    disease_id      uuid references public.diseases(id) on delete set null,
    image_url       text not null,             -- Supabase Storage path
    confidence      numeric(5,2),              -- 0.00–100.00
    risk_level      public.risk_level,
    ai_raw_result   jsonb,                     -- full AI response payload (for debugging/logging)
    notes           text,                      -- optional user note
    scanned_at      timestamptz not null default now()
);
comment on table public.scans is
  'Every crop scan a farmer performs. crop_id and disease_id resolved from AI output.';

create index idx_scans_user_id     on public.scans(user_id);
create index idx_scans_scanned_at  on public.scans(scanned_at desc);


--  5. SOIL HEALTH
--     Stored as time-series so farmers can track changes.

create table public.soil_health_entries (
    id          uuid primary key default uuid_generate_v4(),
    user_id     uuid not null references public.profiles(id) on delete cascade,
    ph          numeric(4,2),                  -- e.g. 7.0
    nitrogen    numeric(6,2),                  -- N value
    phosphorus  numeric(6,2),                  -- P value
    potassium   numeric(6,2),                  -- K value
    notes       text,
    recorded_at timestamptz not null default now()
);
comment on table public.soil_health_entries is
  'Time-series log of soil NPK+pH entries per user. Latest entry = current card shown on screen.';

create index idx_soil_user_id    on public.soil_health_entries(user_id);
create index idx_soil_recorded   on public.soil_health_entries(recorded_at desc);


--  6. WEATHER CACHE
--     Weather is fetched from OpenWeatherMap and cached here
--     so advisories can be stored and served quickly.

create table public.weather_cache (
    id              uuid primary key default uuid_generate_v4(),
    region          text not null,             -- latitude+longitude string or district name
    temperature     numeric(5,2),
    humidity        numeric(5,2),
    wind_speed      numeric(5,2),
    condition       text,                      -- 'Rain', 'Clear', 'Cloudy' etc.
    advisory_spray  text,                      -- generated advisory: 'Rain tomorrow – delay spraying'
    advisory_irrig  text,                      -- irrigation advisory
    advisory_sow    text,                      -- sowing/wind advisory
    forecast_json   jsonb,                     -- 3-day forecast payload
    fetched_at      timestamptz not null default now()
);
comment on table public.weather_cache is
  'Cached weather data and pre-computed advisories per region. Re-fetch after TTL expires.';

create index idx_weather_region on public.weather_cache(region, fetched_at desc);


--  7. COMMUNITY FORUM

create type public.post_category as enum (
    'crop_disease',
    'fertilizer',
    'pesticide',
    'irrigation',
    'weather',
    'general'
);

-- 7a. Questions / posts by farmers
create table public.community_posts (
    id              uuid primary key default uuid_generate_v4(),
    author_id       uuid not null references public.profiles(id) on delete cascade,
    title           text,                      -- optional short title
    body            text not null,             -- the question text
    photo_url       text,                      -- optional attached photo (Supabase Storage)
    category        public.post_category not null default 'general',
    crop_id         uuid references public.crops(id) on delete set null,
    is_resolved     boolean not null default false,
    view_count      int not null default 0,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
comment on table public.community_posts is 'Forum questions posted by farmers.';

create trigger trg_community_posts_updated_at
    before update on public.community_posts
    for each row execute function public.handle_updated_at();

create index idx_posts_author    on public.community_posts(author_id);
create index idx_posts_created   on public.community_posts(created_at desc);
create index idx_posts_category  on public.community_posts(category);


-- 7b. Replies to posts (farmers + experts)
create table public.community_replies (
    id              uuid primary key default uuid_generate_v4(),
    post_id         uuid not null references public.community_posts(id) on delete cascade,
    author_id       uuid not null references public.profiles(id) on delete cascade,
    body            text not null,
    is_verified     boolean not null default false,  -- expert marks this as verified answer
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
comment on table public.community_replies is
  'Replies to community posts. is_verified=true means an expert marked it as the authoritative answer.';

create trigger trg_community_replies_updated_at
    before update on public.community_replies
    for each row execute function public.handle_updated_at();

create index idx_replies_post_id  on public.community_replies(post_id);
create index idx_replies_author   on public.community_replies(author_id);


--  8. EXPERT BROADCASTS

create table public.broadcasts (
    id              uuid primary key default uuid_generate_v4(),
    author_id       uuid not null references public.profiles(id) on delete cascade,
    title           text not null,
    message         text not null,
    target_region   text,                      -- null = all regions
    created_at      timestamptz not null default now()
);
comment on table public.broadcasts is
  'Alert broadcasts sent by verified experts/officers to all farmers (or a target region).';

create index idx_broadcasts_created on public.broadcasts(created_at desc);


--  9. ROW LEVEL SECURITY (RLS)

-- Enable RLS on every table
alter table public.profiles             enable row level security;
alter table public.user_settings        enable row level security;
alter table public.scans                enable row level security;
alter table public.soil_health_entries  enable row level security;
alter table public.community_posts      enable row level security;
alter table public.community_replies    enable row level security;
alter table public.broadcasts           enable row level security;
alter table public.weather_cache        enable row level security;

-- Reference tables are public-read, admin-write
alter table public.crops                enable row level security;
alter table public.diseases             enable row level security;
alter table public.treatments           enable row level security;
alter table public.chatbot_faqs         enable row level security;

-- ── profiles ─────────────────────────────────
create policy "Users can view own profile"
    on public.profiles for select
    using (auth.uid() = id);

create policy "Users can update own profile"
    on public.profiles for update
    using (auth.uid() = id);


-- ── user_settings ──────────────────────────────
create policy "Own settings only"
    on public.user_settings for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── scans ──────────────────────────────────────
create policy "Own scans only"
    on public.scans for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── soil_health_entries ────────────────────────
create policy "Own soil entries only"
    on public.soil_health_entries for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── community_posts ────────────────────────────
create policy "Anyone can read posts"
    on public.community_posts for select
    using (auth.role() = 'authenticated');

create policy "Authors can insert own posts"
    on public.community_posts for insert
    with check (auth.uid() = author_id);

create policy "Authors can update own posts"
    on public.community_posts for update
    using (auth.uid() = author_id);

create policy "Authors can delete own posts"
    on public.community_posts for delete
    using (auth.uid() = author_id);

-- ── community_replies ──────────────────────────
create policy "Anyone can read replies"
    on public.community_replies for select
    using (auth.role() = 'authenticated');

create policy "Authenticated users can insert replies"
    on public.community_replies for insert
    with check (auth.uid() = author_id);

create policy "Reply authors can update own replies"
    on public.community_replies for update
    using (auth.uid() = author_id);

-- Only experts can mark a reply as verified
create policy "Experts can verify replies"
    on public.community_replies for update
    using (
        exists (
            select 1 from public.profiles p
            where p.id = auth.uid() and p.role = 'expert'
        )
    );

-- ── broadcasts ─────────────────────────────────
create policy "Anyone authenticated can read broadcasts"
    on public.broadcasts for select
    using (auth.role() = 'authenticated');

create policy "Only experts can send broadcasts"
    on public.broadcasts for insert
    with check (
        exists (
            select 1 from public.profiles p
            where p.id = auth.uid()
              and p.role = 'expert'
              and p.is_verified_expert = true
        )
    );

-- ── weather_cache ──────────────────────────────
create policy "Authenticated users can read weather"
    on public.weather_cache for select
    using (auth.role() = 'authenticated');

-- Server-side / service role writes weather cache (no user policy needed for insert)

-- ── Reference tables (public read) ─────────────
create policy "Anyone can read crops"       on public.crops        for select using (true);
create policy "Anyone can read diseases"    on public.diseases     for select using (true);
create policy "Anyone can read treatments"  on public.treatments   for select using (true);
create policy "Anyone can read faqs"        on public.chatbot_faqs for select using (true);


--  10. STORED PROCEDURES / FUNCTIONS

--  F1. get_recent_scans(p_user_id, p_limit)
--      Returns last N scans for the home dashboard
--      with crop name, disease name, risk level, and image.

create or replace function public.get_recent_scans(
    p_user_id   uuid,
    p_limit     int default 5
)
returns table (
    scan_id         uuid,
    crop_name       text,
    disease_name    text,
    risk_level      public.risk_level,
    confidence      numeric,
    image_url       text,
    scanned_at      timestamptz
)
language sql stable security definer set search_path = public as $$
    select
        s.id            as scan_id,
        c.name          as crop_name,
        d.name          as disease_name,
        s.risk_level,
        s.confidence,
        s.image_url,
        s.scanned_at
    from public.scans s
    left join public.crops    c on c.id = s.crop_id
    left join public.diseases d on d.id = s.disease_id
    where s.user_id = p_user_id
    order by s.scanned_at desc
    limit p_limit;
$$;

comment on function public.get_recent_scans is
  'Returns the N most recent scans for a user, used on the Home dashboard Recent Scans row.';


--  F2. get_scan_detail(p_scan_id, p_user_id)
--      Returns full scan result: disease detail + treatment.
--      Checks ownership.

create or replace function public.get_scan_detail(
    p_scan_id   uuid,
    p_user_id   uuid
)
returns table (
    scan_id         uuid,
    crop_name       text,
    disease_name    text,
    risk_level      public.risk_level,
    confidence      numeric,
    image_url       text,
    causes          text,
    symptoms        text,
    prevention      text,
    chemical_name   text,
    dosage          text,
    frequency       text,
    disclaimer      text,
    scanned_at      timestamptz
)
language sql stable security definer set search_path = public as $$
    select
        s.id                as scan_id,
        c.name              as crop_name,
        d.name              as disease_name,
        s.risk_level,
        s.confidence,
        s.image_url,
        d.causes,
        d.symptoms,
        d.prevention,
        t.chemical_name,
        t.dosage,
        t.frequency,
        t.disclaimer,
        s.scanned_at
    from public.scans s
    left join public.crops      c  on c.id  = s.crop_id
    left join public.diseases   d  on d.id  = s.disease_id
    left join public.treatments t  on t.disease_id = d.id
    where s.id      = p_scan_id
      and s.user_id = p_user_id
    limit 1;   -- take first treatment if multiple exist
$$;

comment on function public.get_scan_detail is
  'Returns full result + treatment + disease details for a single scan. Used on Result/Treatment/Details screens.';


--  F3. save_scan_result(...)
--      Inserts a new scan row after AI returns its result.
--      Resolves crop_id and disease_id from names.

create or replace function public.save_scan_result(
    p_user_id       uuid,
    p_image_url     text,
    p_crop_name     text,
    p_disease_name  text,
    p_confidence    numeric,
    p_risk_level    public.risk_level,
    p_ai_raw        jsonb default null
)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
    v_crop_id    uuid;
    v_disease_id uuid;
    v_scan_id    uuid;
begin
    -- Resolve crop (insert if unknown to keep data clean)
    select id into v_crop_id from public.crops where name = p_crop_name limit 1;

    -- Resolve disease
    select id into v_disease_id
    from public.diseases
    where name = p_disease_name
      and (v_crop_id is null or crop_id = v_crop_id)
    limit 1;

    insert into public.scans (
        user_id, image_url, crop_id, disease_id,
        confidence, risk_level, ai_raw_result
    ) values (
        p_user_id, p_image_url, v_crop_id, v_disease_id,
        p_confidence, p_risk_level, p_ai_raw
    )
    returning id into v_scan_id;

    return v_scan_id;
end;
$$;

comment on function public.save_scan_result is
  'Called after the AI model returns. Resolves crop/disease by name and inserts the scan record.';


--  F4. get_latest_soil_health(p_user_id)
--      Returns the most recent soil card values for the
--      Soil Health screen.

create or replace function public.get_latest_soil_health(p_user_id uuid)
returns table (
    entry_id    uuid,
    ph          numeric,
    nitrogen    numeric,
    phosphorus  numeric,
    potassium   numeric,
    recorded_at timestamptz
)
language sql stable security definer set search_path = public as $$
    select id, ph, nitrogen, phosphorus, potassium, recorded_at
    from public.soil_health_entries
    where user_id = p_user_id
    order by recorded_at desc
    limit 1;
$$;


-- ────────────────────────────────────────────────────────────
--  F5. upsert_soil_health(...)
--      Inserts a new soil entry (keeps full history).
-- ────────────────────────────────────────────────────────────
create or replace function public.upsert_soil_health(
    p_user_id   uuid,
    p_ph        numeric,
    p_n         numeric,
    p_p         numeric,
    p_k         numeric,
    p_notes     text default null
)
returns uuid
language plpgsql security definer set search_path = public as $$
declare v_id uuid;
begin
    insert into public.soil_health_entries (user_id, ph, nitrogen, phosphorus, potassium, notes)
    values (p_user_id, p_ph, p_n, p_p, p_k, p_notes)
    returning id into v_id;
    return v_id;
end;
$$;

comment on function public.upsert_soil_health is
  'Inserts a new soil health reading. Each tap of Update on the Soil Health screen creates a new row.';


-- ────────────────────────────────────────────────────────────
--  F6. get_community_posts(p_category, p_search, p_limit, p_offset)
--      Returns paginated community feed with reply count
--      and verified-answer indicator.
-- ────────────────────────────────────────────────────────────
create or replace function public.get_community_posts(
    p_category  text    default null,
    p_search    text    default null,
    p_limit     int     default 20,
    p_offset    int     default 0
)
returns table (
    post_id         uuid,
    author_name     text,
    body            text,
    category        public.post_category,
    photo_url       text,
    is_resolved     boolean,
    reply_count     bigint,
    has_verified    boolean,
    created_at      timestamptz
)
language sql stable security definer set search_path = public as $$
    select
        cp.id                           as post_id,
        pr.full_name                    as author_name,
        cp.body,
        cp.category,
        cp.photo_url,
        cp.is_resolved,
        count(cr.id)                    as reply_count,
        bool_or(cr.is_verified)         as has_verified,
        cp.created_at
    from public.community_posts cp
    join public.profiles pr on pr.id = cp.author_id
    left join public.community_replies cr on cr.post_id = cp.id
    where (p_category is null or cp.category::text = p_category)
      and (p_search   is null or cp.body ilike '%' || p_search || '%')
    group by cp.id, pr.full_name
    order by cp.created_at desc
    limit p_limit offset p_offset;
$$;

comment on function public.get_community_posts is
  'Paginated community feed with reply counts and verified-answer badge. Used on Community screen.';


-- ────────────────────────────────────────────────────────────
--  F7. get_post_detail(p_post_id)
--      Returns a single post + all its replies, ordered
--      so verified replies appear first.
-- ────────────────────────────────────────────────────────────
create or replace function public.get_post_detail(p_post_id uuid)
returns table (
    reply_id        uuid,
    author_name     text,
    author_role     public.user_role,
    is_verified     boolean,
    body            text,
    created_at      timestamptz
)
language sql stable security definer set search_path = public as $$
    select
        cr.id                   as reply_id,
        pr.full_name            as author_name,
        pr.role                 as author_role,
        cr.is_verified,
        cr.body,
        cr.created_at
    from public.community_replies cr
    join public.profiles pr on pr.id = cr.author_id
    where cr.post_id = p_post_id
    order by cr.is_verified desc, cr.created_at asc;
$$;

comment on function public.get_post_detail is
  'Returns all replies for a post, verified expert answers first. Used on Question detail screen.';


-- ────────────────────────────────────────────────────────────
--  F8. submit_community_post(...)
--      Farmer submits a new question.
-- ────────────────────────────────────────────────────────────
create or replace function public.submit_community_post(
    p_author_id uuid,
    p_body      text,
    p_category  public.post_category default 'general',
    p_photo_url text default null,
    p_crop_id   uuid default null
)
returns uuid
language plpgsql security definer set search_path = public as $$
declare v_id uuid;
begin
    insert into public.community_posts (author_id, body, category, photo_url, crop_id)
    values (p_author_id, p_body, p_category, p_photo_url, p_crop_id)
    returning id into v_id;
    return v_id;
end;
$$;


-- ────────────────────────────────────────────────────────────
--  F9. submit_community_reply(...)
--      Any authenticated user can reply. is_verified
--      can only be set true if caller is an expert.
-- ────────────────────────────────────────────────────────────
create or replace function public.submit_community_reply(
    p_post_id       uuid,
    p_author_id     uuid,
    p_body          text,
    p_is_verified   boolean default false
)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
    v_id        uuid;
    v_is_expert boolean;
begin
    -- Only allow is_verified=true if caller is a verified expert
    select (role = 'expert' and is_verified_expert = true)
    into v_is_expert
    from public.profiles where id = p_author_id;

    if p_is_verified and not coalesce(v_is_expert, false) then
        raise exception 'Only verified experts can mark a reply as verified.';
    end if;

    insert into public.community_replies (post_id, author_id, body, is_verified)
    values (p_post_id, p_author_id, p_body, p_is_verified and v_is_expert)
    returning id into v_id;

    -- Auto-resolve the post if a verified answer was submitted
    if p_is_verified and v_is_expert then
        update public.community_posts
        set is_resolved = true
        where id = p_post_id;
    end if;

    return v_id;
end;
$$;

comment on function public.submit_community_reply is
  'Submit a reply. Guards the is_verified flag — only verified experts can set it true.';


-- ────────────────────────────────────────────────────────────
--  F10. get_expert_dashboard_stats(p_expert_id)
--       Returns the four counters shown on the Expert
--       Dashboard: pending, answered, today, urgent.
--       "Urgent" = posts older than 24 h with no replies.
-- ────────────────────────────────────────────────────────────
create or replace function public.get_expert_dashboard_stats(p_expert_id uuid)
returns table (
    pending     bigint,
    answered    bigint,
    today       bigint,
    urgent      bigint
)
language sql stable security definer set search_path = public as $$
    with reply_counts as (
        select post_id, count(*) as cnt
        from public.community_replies
        group by post_id
    )
    select
        count(*) filter (where rc.cnt is null or rc.cnt = 0)     as pending,
        count(*) filter (where rc.cnt > 0)                       as answered,
        count(*) filter (
            where cp.created_at >= current_date
        )                                                         as today,
        count(*) filter (
            where (rc.cnt is null or rc.cnt = 0)
              and cp.created_at < now() - interval '24 hours'
        )                                                         as urgent
    from public.community_posts cp
    left join reply_counts rc on rc.post_id = cp.id;
$$;

comment on function public.get_expert_dashboard_stats is
  'Computes the four counters shown on the Expert Dashboard screen.';


-- ────────────────────────────────────────────────────────────
--  F11. get_pending_questions(p_limit, p_offset)
--       Returns unanswered posts for the expert queue.
-- ────────────────────────────────────────────────────────────
create or replace function public.get_pending_questions(
    p_limit     int default 20,
    p_offset    int default 0
)
returns table (
    post_id         uuid,
    author_name     text,
    body            text,
    photo_url       text,
    category        public.post_category,
    created_at      timestamptz
)
language sql stable security definer set search_path = public as $$
    select
        cp.id,
        pr.full_name,
        cp.body,
        cp.photo_url,
        cp.category,
        cp.created_at
    from public.community_posts cp
    join public.profiles pr on pr.id = cp.author_id
    where cp.is_resolved = false
      and not exists (
          select 1 from public.community_replies cr
          where cr.post_id = cp.id
      )
    order by cp.created_at asc       -- oldest first (most urgent)
    limit p_limit offset p_offset;
$$;

comment on function public.get_pending_questions is
  'Returns unanswered community posts for the expert queue, oldest first.';


-- ────────────────────────────────────────────────────────────
--  F12. send_broadcast(p_expert_id, p_title, p_message, p_region)
--       Expert sends a broadcast alert.
-- ────────────────────────────────────────────────────────────
create or replace function public.send_broadcast(
    p_expert_id     uuid,
    p_title         text,
    p_message       text,
    p_region        text default null
)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
    v_id        uuid;
    v_is_expert boolean;
begin
    select (role = 'expert' and is_verified_expert = true)
    into v_is_expert
    from public.profiles where id = p_expert_id;

    if not coalesce(v_is_expert, false) then
        raise exception 'Only verified experts can send broadcasts.';
    end if;

    insert into public.broadcasts (author_id, title, message, target_region)
    values (p_expert_id, p_title, p_message, p_region)
    returning id into v_id;

    return v_id;
end;
$$;

comment on function public.send_broadcast is
  'Inserts a broadcast after verifying the caller is a verified expert.';


-- ────────────────────────────────────────────────────────────
--  F13. get_broadcasts(p_region, p_limit)
--       Returns recent broadcasts for a farmer's region
--       (or all broadcasts if region is null/unmatched).
-- ────────────────────────────────────────────────────────────
create or replace function public.get_broadcasts(
    p_region    text    default null,
    p_limit     int     default 10
)
returns table (
    broadcast_id    uuid,
    author_name     text,
    title           text,
    message         text,
    target_region   text,
    created_at      timestamptz
)
language sql stable security definer set search_path = public as $$
    select
        b.id,
        pr.full_name,
        b.title,
        b.message,
        b.target_region,
        b.created_at
    from public.broadcasts b
    join public.profiles pr on pr.id = b.author_id
    where b.target_region is null
       or b.target_region = p_region
    order by b.created_at desc
    limit p_limit;
$$;


-- ────────────────────────────────────────────────────────────
--  F14. update_user_settings(p_user_id, p_language, p_voice)
--       Upserts user settings (language + voice guidance).
-- ────────────────────────────────────────────────────────────
create or replace function public.update_user_settings(
    p_user_id   uuid,
    p_language  public.app_language,
    p_voice     boolean
)
returns void
language plpgsql security definer set search_path = public as $$
begin
    insert into public.user_settings (user_id, language, voice_guidance)
    values (p_user_id, p_language, p_voice)
    on conflict (user_id) do update
        set language       = excluded.language,
            voice_guidance = excluded.voice_guidance,
            updated_at     = now();

    -- Mirror back to profile for quick access
    update public.profiles
    set language          = p_language,
        voice_assistance  = p_voice
    where id = p_user_id;
end;
$$;

comment on function public.update_user_settings is
  'Upserts user_settings and mirrors language/voice back to profiles for quick access.';


-- ────────────────────────────────────────────────────────────
--  F15. complete_onboarding(p_user_id, p_language, p_voice, p_name)
--       Called at the end of onboarding (Welcome screen).
-- ────────────────────────────────────────────────────────────
create or replace function public.complete_onboarding(
    p_user_id   uuid,
    p_full_name text,
    p_language  public.app_language default 'en',
    p_voice     boolean default false
)
returns void
language plpgsql security definer set search_path = public as $$
begin
    update public.profiles
    set full_name           = p_full_name,
        language            = p_language,
        voice_assistance    = p_voice,
        onboarding_complete = true
    where id = p_user_id;

    -- Create settings row
    perform public.update_user_settings(p_user_id, p_language, p_voice);
end;
$$;

comment on function public.complete_onboarding is
  'Called once after the onboarding flow. Sets name, language, voice pref, and flips onboarding_complete.';


-- ────────────────────────────────────────────────────────────
--  F16. get_chatbot_faqs(p_category, p_language)
--       Returns FAQ items for the Chatbot screen,
--       localised if a non-English language is requested.
-- ────────────────────────────────────────────────────────────
create or replace function public.get_chatbot_faqs(
    p_category  text default null,
    p_language  text default 'en'
)
returns table (
    faq_id      uuid,
    category    text,
    question    text,
    answer      text,
    sort_order  int
)
language sql stable security definer set search_path = public as $$
    select
        id,
        category,
        case p_language
            when 'ur' then coalesce(question_ur, question)
            when 'pa' then coalesce(question_pa, question)
            else question
        end as question,
        case p_language
            when 'ur' then coalesce(answer_ur, answer)
            when 'pa' then coalesce(answer_pa, answer)
            else answer
        end as answer,
        sort_order
    from public.chatbot_faqs
    where (p_category is null or category = p_category)
    order by sort_order asc;
$$;

comment on function public.get_chatbot_faqs is
  'Returns localised FAQ rows for the Chatbot screen. Falls back to English if translation is missing.';


--  11. SEED DATA  (reference tables — run once)

-- Crops
insert into public.crops (name, name_ur, name_pa) values
    ('Wheat',  'گندم',    'ਕਣਕ'),
    ('Rice',   'چاول',    'ਚੌਲ'),
    ('Maize',  'مکئی',    'ਮੱਕੀ');

-- Diseases (sample — expand as AI model evolves)
with c as (select id, name from public.crops)
insert into public.diseases (crop_id, name, name_ur, causes, symptoms, prevention, risk_default)
select
    c.id,
    d.name,
    d.name_ur,
    d.causes,
    d.symptoms,
    d.prevention,
    d.risk_default::public.risk_level
from c
join (values
    ('Wheat', 'Leaf Blight',  'پتی جھلساؤ',
     'Fungus due to high humidity',
     'Brown spots on leaves, yellow edges',
     'Ensure good airflow, avoid overhead watering',
     'high'),
    ('Wheat', 'Rust',         'زنگ',
     'Airborne fungal spores, warm moist conditions',
     'Orange/brown pustules on leaves',
     'Use resistant varieties, apply fungicide early',
     'medium'),
    ('Rice',  'Blast',        'دھماکہ',
     'Fungal pathogen Magnaporthe oryzae',
     'Diamond-shaped lesions on leaves',
     'Balanced nitrogen, avoid dense planting',
     'high'),
    ('Maize', 'Northern Leaf Blight', 'شمالی پتی جھلساؤ',
     'Fungus Exserohilum turcicum',
     'Long greyish-green lesions on leaves',
     'Rotate crops, remove infected debris',
     'medium')
) as d(crop_name, name, name_ur, causes, symptoms, prevention, risk_default)
on c.name = d.crop_name;

-- Treatments
with dis as (select id, name from public.diseases)
insert into public.treatments (disease_id, chemical_name, dosage, frequency)
select
    dis.id,
    t.chemical_name,
    t.dosage,
    t.frequency
from dis
join (values
    ('Leaf Blight',           'Copper Oxychloride',   '2g per liter water',    'Every 5 days'),
    ('Rust',                  'Mancozeb 80% WP',      '2.5g per liter water',  'Every 7 days'),
    ('Blast',                 'Tricyclazole 75% WP',  '0.6g per liter water',  'Every 10 days'),
    ('Northern Leaf Blight',  'Propiconazole 25% EC', '1ml per liter water',   'Every 14 days')
) as t(disease_name, chemical_name, dosage, frequency)
on dis.name = t.disease_name;

-- Chatbot FAQs
insert into public.chatbot_faqs (category, question, answer, sort_order) values
    ('How to scan', 'How to scan a crop?',
     'Open the Scan tab, tap the camera button, and position your leaf inside the white box. Tap capture.',
     1),
    ('How to scan', 'What do colors mean?',
     'Red = High Risk, Orange = Medium Risk, Green = Healthy or Low Risk.',
     2),
    ('Disease info', 'What is Leaf Blight?',
     'A fungal disease causing brown spots on leaves. Apply Copper Oxychloride as recommended.',
     3),
    ('Pesticide', 'How do I apply pesticide safely?',
     'Wear gloves and a mask. Spray early morning or late evening. Always follow dosage instructions.',
     4),
    ('Weather', 'Should I spray before rain?',
     'No. Avoid spraying 24 hours before expected rain as it reduces effectiveness.',
     5);


--  12. CHATBOT HISTORY
create table public.chatbot (
    id          uuid primary key default uuid_generate_v4(),
    user_id     uuid not null references public.profiles(id) on delete cascade,
    question    text not null,
    answer      text not null,
    language    text not null,
    created_at  timestamptz not null default now()
);
comment on table public.chatbot is 'Chatbot message history per user.';

create index idx_chatbot_user_id on public.chatbot(user_id);
create index idx_chatbot_created_at on public.chatbot(created_at desc);

alter table public.chatbot enable row level security;

create policy "Own chatbot history"
    on public.chatbot for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);