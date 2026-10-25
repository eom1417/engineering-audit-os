-- The orders and the notes people keep on them: each person reaches only their own.
create table public.orders (
  id bigint generated always as identity primary key,
  owner uuid not null references auth.users (id),
  item text not null,
  price numeric not null,
  quantity integer not null default 1
);
alter table public.orders enable row level security;
create policy "owners read their orders" on public.orders for select using (auth.uid() = owner);
create policy "owners change their orders" on public.orders for update using (auth.uid() = owner) with check (auth.uid() = owner);

create table public.notes (
  id bigint generated always as identity primary key,
  order_id bigint references public.orders (id),
  owner uuid not null references auth.users (id),
  body text not null
);
alter table public.notes enable row level security;
create policy "owners keep their notes" on public.notes for all using (auth.uid() = owner) with check (auth.uid() = owner);
