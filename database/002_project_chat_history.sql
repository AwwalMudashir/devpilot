create table if not exists public.project_chat_messages (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.devpilot_users(id) on delete cascade,
    project_id uuid not null references public.projects(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null check (char_length(content) between 1 and 20000),
    created_at timestamptz not null default now()
);

create index if not exists project_chat_messages_conversation_idx
    on public.project_chat_messages(user_id, project_id, created_at desc);

alter table public.project_chat_messages enable row level security;

create or replace function public.trim_project_chat_messages()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from public.project_chat_messages
    where id in (
        select id
        from public.project_chat_messages
        where user_id = new.user_id
          and project_id = new.project_id
        order by created_at desc, id desc
        offset 40
    );

    return new;
end;
$$;

drop trigger if exists trim_project_chat_messages_after_insert
    on public.project_chat_messages;

create trigger trim_project_chat_messages_after_insert
after insert on public.project_chat_messages
for each row
execute function public.trim_project_chat_messages();

comment on table public.project_chat_messages is
    'Project-scoped DevPilot conversation history, limited to 40 messages per user and project';

notify pgrst, 'reload schema';
