create extension if not exists pgcrypto;

create table if not exists public.devpilot_users (
    id uuid primary key default gen_random_uuid(),
    github_user_id bigint not null unique,
    github_login text not null,
    github_name text,
    avatar_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.github_installations (
    id bigint primary key,
    account_id bigint not null,
    account_login text not null,
    account_type text not null,
    repository_selection text not null default 'selected',
    permissions jsonb not null default '{}'::jsonb,
    suspended_at timestamptz,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.user_installations (
    user_id uuid not null references public.devpilot_users(id) on delete cascade,
    installation_id bigint not null references public.github_installations(id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (user_id, installation_id)
);

create table if not exists public.devpilot_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.devpilot_users(id) on delete cascade,
    token_hash text not null unique,
    expires_at timestamptz not null,
    created_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);

create index if not exists devpilot_sessions_user_id_idx
    on public.devpilot_sessions(user_id);

create index if not exists devpilot_sessions_expires_at_idx
    on public.devpilot_sessions(expires_at);

alter table public.projects
    add column if not exists user_id uuid references public.devpilot_users(id) on delete cascade,
    add column if not exists github_installation_id bigint references public.github_installations(id) on delete cascade,
    add column if not exists github_repo_id bigint,
    add column if not exists github_full_name text,
    add column if not exists github_private boolean not null default false,
    add column if not exists github_default_branch text,
    add column if not exists github_access_revoked_at timestamptz;

create unique index if not exists projects_user_github_repo_idx
    on public.projects(user_id, github_repo_id)
    where user_id is not null and github_repo_id is not null;

create index if not exists projects_installation_idx
    on public.projects(github_installation_id);

create table if not exists public.github_webhook_deliveries (
    delivery_id text primary key,
    event_name text not null,
    action text,
    received_at timestamptz not null default now()
);

alter table public.devpilot_users enable row level security;
alter table public.github_installations enable row level security;
alter table public.user_installations enable row level security;
alter table public.devpilot_sessions enable row level security;
alter table public.github_webhook_deliveries enable row level security;

comment on table public.devpilot_users is
    'GitHub identities that have connected to DevPilot';
comment on table public.github_installations is
    'GitHub App installations known to DevPilot';
comment on table public.user_installations is
    'Users allowed to access each GitHub App installation';
comment on table public.devpilot_sessions is
    'Hashed, revocable DevPilot browser sessions';
comment on column public.projects.github_access_revoked_at is
    'Set when an installation no longer grants access to the repository';
