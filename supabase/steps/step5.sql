-- Night Out setup, step 5 of 6
alter table public.profiles enable row level security;

alter table public.plans    enable row level security;

alter table public.follows  enable row level security;
