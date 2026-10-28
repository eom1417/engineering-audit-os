-- The brands the invoices show, each with its logo.
create table public.brands (
  id bigint generated always as identity primary key,
  name text not null,
  logo text
);
alter table public.brands enable row level security;
create policy "anyone reads the brands" on public.brands for select using (true);

insert into public.brands (name, logo) values
  ('Main', 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==');
