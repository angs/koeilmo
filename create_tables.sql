CREATE TABLE public.exams (
	examid int4 DEFAULT nextval('exams_id_seq'::regclass) NOT NULL,
	examdate date NULL,
	topic text NULL,
	teacher text NULL,
	additional_info text NULL,
	assignee text NULL,
	date_added timestamp NULL,
	CONSTRAINT exams_pkey PRIMARY KEY (examid)
);