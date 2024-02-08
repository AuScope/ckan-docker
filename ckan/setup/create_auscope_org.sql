do $$
declare
    user_id text;
begin

SELECT id INTO user_id FROM public.user WHERE name='ckan_admin';

INSERT INTO public.group (id, name, title, description, state, type, approval_status, image_url, is_organization) VALUES ('12345678-1234-1234-1234-123456789012', 'AuScope', 'AuScope Australia', 'AuScope is Australia''s provider of research infrastructure to the national geoscience community working on fundamental geoscience questions and grand challenges — climate change, natural resources security and natural hazards. We are funded by the Australian Government via the Department of Education (NCRIS). You can find our team, tools, data, analytics and services at Geoscience Australia, CSIRO, state and territory geological surveys and universities across the Australian continent.', 'active', 'organization', 'approved', 'https://images.squarespace-cdn.com/content/v1/5b440dc18ab722131f76b631/1544673461662-GWIIUQIW3A490WP1RHBV/AuScope+Logo_no+space_+-+horizontal+tagline_+-+horizontal+tagline.png', true);

INSERT INTO public.member (id, group_id, table_id, state, table_name, capacity) VALUES ('abcdefgh-abcd-abcd-abcd-abcdefghijkl', '12345678-1234-1234-1234-123456789012', user_id, 'active', 'user', 'admin');

end; $$;
