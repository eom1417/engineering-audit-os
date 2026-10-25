-- The orders and the notes people keep on them.
create table public.orders (
  id bigint generated always as identity primary key,
  owner uuid not null references auth.users (id),
  item text not null,
  price numeric not null,
  quantity integer not null default 1
);
alter table public.orders enable row level security;
create policy "owners read their orders" on public.orders for select using (auth.uid() = owner);
create policy "anyone can change orders" on public.orders for update using (true);

create table public.notes (
  id bigint generated always as identity primary key,
  order_id bigint references public.orders (id),
  body text not null
);
