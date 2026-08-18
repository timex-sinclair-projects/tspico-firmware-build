; z80dasm 1.2.0
; command line: z80dasm -a -l -t -g 0x0000 -o docs/rom-analysis/disasm/genuine-2068-exrom.asm -s docs/rom-analysis/disasm/genuine-2068-exrom.sym ROMs/GENUINE-2068-exrom.bin

	org 00000h

l0000h:
	di			;0000	f3		.
l0001h:
	jr l0049h		;0001	18 46		. F
	rst 38h			;0003	ff		.
l0004h:
	rst 38h			;0004	ff		.
l0005h:
	rst 38h			;0005	ff		.
l0006h:
	rst 38h			;0006	ff		.
	rst 38h			;0007	ff		.
l0008h:
	ld hl,(05c5dh)		;0008	2a 5d 5c	* ] \
l000bh:
	ld (05c5fh),hl		;000b	22 5f 5c	" _ \
	pop hl			;000e	e1		.
	ld l,(hl)		;000f	6e		n
l0010h:
	ld (iy+000h),l		;0010	fd 75 00	. u .
	ld sp,(05c3dh)		;0013	ed 7b 3d 5c	. { = \
l0017h:
	ld hl,l1354h		;0017	21 54 13	! T .
	push hl			;001a	e5		.
	ld h,0ffh		;001b	26 ff		& .
	ld l,000h		;001d	2e 00		. .
	push hl			;001f	e5		.
l0020h:
	push af			;0020	f5		.
	ld a,(05cc2h)		;0021	3a c2 5c	: . \
	and a			;0024	a7		.
	nop			;0025	00		.
	jr z,l002ch		;0026	28 04		( .
	pop af			;0028	f1		.
	call 0fd32h		;0029	cd 32 fd	. 2 .
l002ch:
	pop af			;002c	f1		.
	call 06572h		;002d	cd 72 65	. r e
l0030h:
	rst 38h			;0030	ff		.
	rst 38h			;0031	ff		.
	rst 38h			;0032	ff		.
	rst 38h			;0033	ff		.
	rst 38h			;0034	ff		.
	rst 38h			;0035	ff		.
	rst 38h			;0036	ff		.
	rst 38h			;0037	ff		.
l0038h:
	push af			;0038	f5		.
	di			;0039	f3		.
	ld a,(05cc2h)		;003a	3a c2 5c	: . \
	and a			;003d	a7		.
	nop			;003e	00		.
	jr z,l0045h		;003f	28 04		( .
	pop af			;0041	f1		.
	jp 0fa6eh		;0042	c3 6e fa	. n .
l0045h:
	pop af			;0045	f1		.
	jp 062aeh		;0046	c3 ae 62	. . b
l0049h:
	ld a,001h		;0049	3e 01		> .
	out (0f4h),a		;004b	d3 f4		. .
	jr l005ah		;004d	18 0b		. .
l004fh:
	xor a			;004f	af		.
	out (0f4h),a		;0050	d3 f4		. .
	out (0ffh),a		;0052	d3 ff		. .
	ld de,0ffffh		;0054	11 ff ff	. . .
	jp l0d31h		;0057	c3 31 0d	. 1 .
l005ah:
	ld hl,l004fh		;005a	21 4f 00	! O .
	ld de,06000h		;005d	11 00 60	. . `
	ld bc,l000bh		;0060	01 0b 00	. . .
	ldir			;0063	ed b0		. .
	jp 06000h		;0065	c3 00 60	. . `
sub_0068h:
	ld hl,l00e5h		;0068	21 e5 00	! . .
	push hl			;006b	e5		.
	ld hl,01f80h		;006c	21 80 1f	! . .
	bit 7,a			;006f	cb 7f		. .
	jr z,l0076h		;0071	28 03		( .
	ld hl,00c98h		;0073	21 98 0c	! . .
l0076h:
	ex af,af'		;0076	08		.
	inc de			;0077	13		.
	dec ix			;0078	dd 2b		. +
	di			;007a	f3		.
	ld a,002h		;007b	3e 02		> .
	ld b,a			;007d	47		G
l007eh:
	djnz l007eh		;007e	10 fe		. .
	out (0feh),a		;0080	d3 fe		. .
	xor 00fh		;0082	ee 0f		. .
	ld b,0a4h		;0084	06 a4		. .
	dec l			;0086	2d		-
	jr nz,l007eh		;0087	20 f5		  .
	dec b			;0089	05		.
	dec h			;008a	25		%
	jp p,l007eh		;008b	f2 7e 00	. ~ .
	ld b,02fh		;008e	06 2f		. /
l0090h:
	djnz l0090h		;0090	10 fe		. .
	out (0feh),a		;0092	d3 fe		. .
	ld a,00dh		;0094	3e 0d		> .
	ld b,037h		;0096	06 37		. 7
l0098h:
	djnz l0098h		;0098	10 fe		. .
	out (0feh),a		;009a	d3 fe		. .
	ld bc,03b0eh		;009c	01 0e 3b	. . ;
	ex af,af'		;009f	08		.
	ld l,a			;00a0	6f		o
	jp l00adh		;00a1	c3 ad 00	. . .
l00a4h:
	ld a,d			;00a4	7a		z
	or e			;00a5	b3		.
	jr z,l00b4h		;00a6	28 0c		( .
	ld l,(ix+000h)		;00a8	dd 6e 00	. n .
l00abh:
	ld a,h			;00ab	7c		|
	xor l			;00ac	ad		.
l00adh:
	ld h,a			;00ad	67		g
	ld a,001h		;00ae	3e 01		> .
	scf			;00b0	37		7
	jp l00cbh		;00b1	c3 cb 00	. . .
l00b4h:
	ld l,h			;00b4	6c		l
	jr l00abh		;00b5	18 f4		. .
l00b7h:
	ld a,c			;00b7	79		y
	bit 7,b			;00b8	cb 78		. x
l00bah:
	djnz l00bah		;00ba	10 fe		. .
	jr nc,l00c2h		;00bc	30 04		0 .
	ld b,042h		;00be	06 42		. B
l00c0h:
	djnz l00c0h		;00c0	10 fe		. .
l00c2h:
	out (0feh),a		;00c2	d3 fe		. .
	ld b,03eh		;00c4	06 3e		. >
	jr nz,l00b7h		;00c6	20 ef		  .
	dec b			;00c8	05		.
	xor a			;00c9	af		.
	inc a			;00ca	3c		<
l00cbh:
	rl l			;00cb	cb 15		. .
	jp nz,l00bah		;00cd	c2 ba 00	. . .
	dec de			;00d0	1b		.
	inc ix			;00d1	dd 23		. #
	ld b,031h		;00d3	06 31		. 1
	ld a,07fh		;00d5	3e 7f		> .
	in a,(0feh)		;00d7	db fe		. .
	rra			;00d9	1f		.
	ret nc			;00da	d0		.
	ld a,d			;00db	7a		z
	inc a			;00dc	3c		<
	jp nz,l00a4h		;00dd	c2 a4 00	. . .
	ld b,03bh		;00e0	06 3b		. ;
l00e2h:
	djnz l00e2h		;00e2	10 fe		. .
	ret			;00e4	c9		.
l00e5h:
	push af			;00e5	f5		.
	ld a,(05c48h)		;00e6	3a 48 5c	: H \
	and 038h		;00e9	e6 38		. 8
	rrca			;00eb	0f		.
	rrca			;00ec	0f		.
	rrca			;00ed	0f		.
	out (0feh),a		;00ee	d3 fe		. .
	ld a,07fh		;00f0	3e 7f		> .
	in a,(0feh)		;00f2	db fe		. .
	rra			;00f4	1f		.
	ei			;00f5	fb		.
	jr c,l00fah		;00f6	38 02		8 .
	rst 8			;00f8	cf		.
	inc c			;00f9	0c		.
l00fah:
	pop af			;00fa	f1		.
	ret			;00fb	c9		.
sub_00fch:
	inc d			;00fc	14		.
	ex af,af'		;00fd	08		.
	dec d			;00fe	15		.
	di			;00ff	f3		.
	ld a,00fh		;0100	3e 0f		> .
	out (0feh),a		;0102	d3 fe		. .
	ld hl,l00e5h		;0104	21 e5 00	! . .
	push hl			;0107	e5		.
	in a,(0feh)		;0108	db fe		. .
	rra			;010a	1f		.
	and 020h		;010b	e6 20		.  
	or 002h			;010d	f6 02		. .
	ld c,a			;010f	4f		O
	cp a			;0110	bf		.
l0111h:
	ret nz			;0111	c0		.
l0112h:
	call sub_018dh		;0112	cd 8d 01	. . .
	jr nc,l0111h		;0115	30 fa		0 .
	ld hl,l0415h		;0117	21 15 04	! . .
l011ah:
	djnz l011ah		;011a	10 fe		. .
	dec hl			;011c	2b		+
	ld a,h			;011d	7c		|
	or l			;011e	b5		.
	jr nz,l011ah		;011f	20 f9		  .
	call sub_0189h		;0121	cd 89 01	. . .
	jr nc,l0111h		;0124	30 eb		0 .
l0126h:
	ld b,09ch		;0126	06 9c		. .
	call sub_0189h		;0128	cd 89 01	. . .
	jr nc,l0111h		;012b	30 e4		0 .
	ld a,0c6h		;012d	3e c6		> .
	cp b			;012f	b8		.
	jr nc,l0112h		;0130	30 e0		0 .
	inc h			;0132	24		$
	jr nz,l0126h		;0133	20 f1		  .
l0135h:
	ld b,0c9h		;0135	06 c9		. .
	call sub_018dh		;0137	cd 8d 01	. . .
	jr nc,l0111h		;013a	30 d5		0 .
	ld a,b			;013c	78		x
	cp 0d4h			;013d	fe d4		. .
	jr nc,l0135h		;013f	30 f4		0 .
	call sub_018dh		;0141	cd 8d 01	. . .
	ret nc			;0144	d0		.
	ld a,c			;0145	79		y
	xor 003h		;0146	ee 03		. .
	ld c,a			;0148	4f		O
	ld h,000h		;0149	26 00		& .
	ld b,0b0h		;014b	06 b0		. .
	jr l016eh		;014d	18 1f		. .
l014fh:
	ex af,af'		;014f	08		.
	jr nz,l0159h		;0150	20 07		  .
	jr nc,l0163h		;0152	30 0f		0 .
	ld (ix+000h),l		;0154	dd 75 00	. u .
	jr l0168h		;0157	18 0f		. .
l0159h:
	rl c			;0159	cb 11		. .
	xor l			;015b	ad		.
	ret nz			;015c	c0		.
	ld a,c			;015d	79		y
	rra			;015e	1f		.
	ld c,a			;015f	4f		O
	inc de			;0160	13		.
	jr l016ah		;0161	18 07		. .
l0163h:
	ld a,(ix+000h)		;0163	dd 7e 00	. ~ .
	xor l			;0166	ad		.
	ret nz			;0167	c0		.
l0168h:
	inc ix			;0168	dd 23		. #
l016ah:
	dec de			;016a	1b		.
	ex af,af'		;016b	08		.
	ld b,0b2h		;016c	06 b2		. .
l016eh:
	ld l,001h		;016e	2e 01		. .
l0170h:
	call sub_0189h		;0170	cd 89 01	. . .
	ret nc			;0173	d0		.
	ld a,0cbh		;0174	3e cb		> .
	cp b			;0176	b8		.
	rl l			;0177	cb 15		. .
	ld b,0b0h		;0179	06 b0		. .
	jp nc,l0170h		;017b	d2 70 01	. p .
	ld a,h			;017e	7c		|
	xor l			;017f	ad		.
	ld h,a			;0180	67		g
	ld a,d			;0181	7a		z
	or e			;0182	b3		.
	jr nz,l014fh		;0183	20 ca		  .
	ld a,h			;0185	7c		|
	cp 001h			;0186	fe 01		. .
	ret			;0188	c9		.
sub_0189h:
	call sub_018dh		;0189	cd 8d 01	. . .
	ret nc			;018c	d0		.
sub_018dh:
	ld a,016h		;018d	3e 16		> .
l018fh:
	dec a			;018f	3d		=
	jr nz,l018fh		;0190	20 fd		  .
	and a			;0192	a7		.
l0193h:
	inc b			;0193	04		.
	ret z			;0194	c8		.
	ld a,07fh		;0195	3e 7f		> .
	in a,(0feh)		;0197	db fe		. .
	rra			;0199	1f		.
	ret nc			;019a	d0		.
	xor c			;019b	a9		.
	and 020h		;019c	e6 20		.  
	jr z,l0193h		;019e	28 f3		( .
	ld a,c			;01a0	79		y
	cpl			;01a1	2f		/
	ld c,a			;01a2	4f		O
	and 007h		;01a3	e6 07		. .
	or 008h			;01a5	f6 08		. .
	out (0feh),a		;01a7	d3 fe		. .
	scf			;01a9	37		7
	ret			;01aa	c9		.
	ld a,(05c74h)		;01ab	3a 74 5c	: t \
	ld bc,l19e1h		;01ae	01 e1 19	. . .
	sub c			;01b1	91		.
	ld (05c74h),a		;01b2	32 74 5c	2 t \
	push ix			;01b5	dd e5		. .
	exx			;01b7	d9		.
	ld hl,l1befh		;01b8	21 ef 1b	! . .
	push hl			;01bb	e5		.
	ld l,000h		;01bc	2e 00		. .
	ld h,0ffh		;01be	26 ff		& .
	push hl			;01c0	e5		.
	ld hl,l0000h		;01c1	21 00 00	! . .
	push hl			;01c4	e5		.
	push hl			;01c5	e5		.
	exx			;01c6	d9		.
	call sub_0f99h		;01c7	cd 99 0f	. . .
	pop ix			;01ca	dd e1		. .
	bit 7,(iy+001h)		;01cc	fd cb 01 7e	. . . ~
	jr z,l0238h		;01d0	28 66		( f
	ld bc,l0010h+1		;01d2	01 11 00	. . .
	ld a,(05c74h)		;01d5	3a 74 5c	: t \
	and a			;01d8	a7		.
	jr z,l01ddh		;01d9	28 02		( .
	ld c,022h		;01db	0e 22		. "
l01ddh:
	push ix			;01dd	dd e5		. .
	exx			;01df	d9		.
	ld hl,l0030h		;01e0	21 30 00	! 0 .
	push hl			;01e3	e5		.
	ld l,000h		;01e4	2e 00		. .
	ld h,0ffh		;01e6	26 ff		& .
	push hl			;01e8	e5		.
	ld hl,l0000h		;01e9	21 00 00	! . .
	push hl			;01ec	e5		.
	push hl			;01ed	e5		.
	exx			;01ee	d9		.
	call sub_0f99h		;01ef	cd 99 0f	. . .
	pop ix			;01f2	dd e1		. .
	push de			;01f4	d5		.
	pop ix			;01f5	dd e1		. .
	ld b,00bh		;01f7	06 0b		. .
	ld a,020h		;01f9	3e 20		>  
l01fbh:
	ld (de),a		;01fb	12		.
	inc de			;01fc	13		.
	djnz l01fbh		;01fd	10 fc		. .
	ld (ix+001h),0ffh	;01ff	dd 36 01 ff	. 6 . .
	push ix			;0203	dd e5		. .
	exx			;0205	d9		.
	ld hl,02fafh		;0206	21 af 2f	! . /
	push hl			;0209	e5		.
	ld l,000h		;020a	2e 00		. .
	ld h,0ffh		;020c	26 ff		& .
	push hl			;020e	e5		.
	ld hl,l0000h		;020f	21 00 00	! . .
	push hl			;0212	e5		.
	push hl			;0213	e5		.
	exx			;0214	d9		.
	call sub_0f99h		;0215	cd 99 0f	. . .
	pop ix			;0218	dd e1		. .
	ld hl,0fff6h		;021a	21 f6 ff	! . .
	dec bc			;021d	0b		.
	add hl,bc		;021e	09		.
	inc bc			;021f	03		.
	jr nc,l0231h		;0220	30 0f		0 .
	ld a,(05c74h)		;0222	3a 74 5c	: t \
	and a			;0225	a7		.
	jr nz,$+4		;0226	20 02		  .
	rst 8			;0228	cf		.
	ld c,078h		;0229	0e 78		. x
	or c			;022b	b1		.
	jr z,l0238h		;022c	28 0a		( .
	ld bc,l0008h+2		;022e	01 0a 00	. . .
l0231h:
	push ix			;0231	dd e5		. .
	pop hl			;0233	e1		.
	inc hl			;0234	23		#
	ex de,hl		;0235	eb		.
	ldir			;0236	ed b0		. .
l0238h:
	push ix			;0238	dd e5		. .
	exx			;023a	d9		.
	ld hl,l0017h+1		;023b	21 18 00	! . .
	push hl			;023e	e5		.
	ld l,000h		;023f	2e 00		. .
	ld h,0ffh		;0241	26 ff		& .
	push hl			;0243	e5		.
	ld hl,l0000h		;0244	21 00 00	! . .
	push hl			;0247	e5		.
	push hl			;0248	e5		.
	exx			;0249	d9		.
	call sub_0f99h		;024a	cd 99 0f	. . .
	pop ix			;024d	dd e1		. .
	cp 0e4h			;024f	fe e4		. .
	jp nz,l02f2h		;0251	c2 f2 02	. . .
	ld a,(05c74h)		;0254	3a 74 5c	: t \
	cp 003h			;0257	fe 03		. .
	jp z,l08d9h		;0259	ca d9 08	. . .
	push ix			;025c	dd e5		. .
	exx			;025e	d9		.
	ld hl,l0020h		;025f	21 20 00	!   .
	push hl			;0262	e5		.
	ld l,000h		;0263	2e 00		. .
	ld h,0ffh		;0265	26 ff		& .
	push hl			;0267	e5		.
	ld hl,l0000h		;0268	21 00 00	! . .
	push hl			;026b	e5		.
	push hl			;026c	e5		.
	exx			;026d	d9		.
	call sub_0f99h		;026e	cd 99 0f	. . .
	exx			;0271	d9		.
	ld hl,02c70h		;0272	21 70 2c	! p ,
	push hl			;0275	e5		.
	ld l,000h		;0276	2e 00		. .
	ld h,0ffh		;0278	26 ff		& .
	push hl			;027a	e5		.
	ld hl,l0000h		;027b	21 00 00	! . .
	push hl			;027e	e5		.
	push hl			;027f	e5		.
	exx			;0280	d9		.
	call sub_0f99h		;0281	cd 99 0f	. . .
	pop ix			;0284	dd e1		. .
	set 7,c			;0286	cb f9		. .
	jr nc,$+13		;0288	30 0b		0 .
	ld hl,l0000h		;028a	21 00 00	! . .
	ld a,(05c74h)		;028d	3a 74 5c	: t \
	dec a			;0290	3d		=
	jr z,l02a9h		;0291	28 16		( .
	rst 8			;0293	cf		.
	ld bc,0d9c2h		;0294	01 c2 d9	. . .
	ex af,af'		;0297	08		.
	bit 7,(iy+001h)		;0298	fd cb 01 7e	. . . ~
	jr z,l02b6h		;029c	28 18		( .
	inc hl			;029e	23		#
	ld a,(hl)		;029f	7e		~
	ld (ix+00bh),a		;02a0	dd 77 0b	. w .
	inc hl			;02a3	23		#
	ld a,(hl)		;02a4	7e		~
	ld (ix+00ch),a		;02a5	dd 77 0c	. w .
	inc hl			;02a8	23		#
l02a9h:
	ld (ix+00eh),c		;02a9	dd 71 0e	. q .
	ld a,001h		;02ac	3e 01		> .
	bit 6,c			;02ae	cb 71		. q
	jr z,l02b3h		;02b0	28 01		( .
	inc a			;02b2	3c		<
l02b3h:
	ld (ix+000h),a		;02b3	dd 77 00	. w .
l02b6h:
	ex de,hl		;02b6	eb		.
	push ix			;02b7	dd e5		. .
	exx			;02b9	d9		.
	ld hl,l0020h		;02ba	21 20 00	!   .
	push hl			;02bd	e5		.
	ld l,000h		;02be	2e 00		. .
	ld h,0ffh		;02c0	26 ff		& .
	push hl			;02c2	e5		.
	ld hl,l0000h		;02c3	21 00 00	! . .
	push hl			;02c6	e5		.
	push hl			;02c7	e5		.
	exx			;02c8	d9		.
	call sub_0f99h		;02c9	cd 99 0f	. . .
	pop ix			;02cc	dd e1		. .
	cp 029h			;02ce	fe 29		. )
	jr nz,$-59		;02d0	20 c3		  .
	push ix			;02d2	dd e5		. .
	exx			;02d4	d9		.
	ld hl,l0020h		;02d5	21 20 00	!   .
	push hl			;02d8	e5		.
	ld l,000h		;02d9	2e 00		. .
	ld h,0ffh		;02db	26 ff		& .
	push hl			;02dd	e5		.
	ld hl,l0000h		;02de	21 00 00	! . .
sub_02e1h:
	push hl			;02e1	e5		.
	push hl			;02e2	e5		.
	exx			;02e3	d9		.
	call sub_0f99h		;02e4	cd 99 0f	. . .
	pop ix			;02e7	dd e1		. .
	bit 7,(iy+001h)		;02e9	fd cb 01 7e	. . . ~
	ret z			;02ed	c8		.
	ex de,hl		;02ee	eb		.
	jp l04c9h		;02ef	c3 c9 04	. . .
l02f2h:
	cp 0aah			;02f2	fe aa		. .
	jr nz,l032eh		;02f4	20 38		  8
	ld a,(05c74h)		;02f6	3a 74 5c	: t \
	cp 003h			;02f9	fe 03		. .
	jp z,l08d9h		;02fb	ca d9 08	. . .
	push ix			;02fe	dd e5		. .
	exx			;0300	d9		.
	ld hl,l0020h		;0301	21 20 00	!   .
	push hl			;0304	e5		.
	ld l,000h		;0305	2e 00		. .
	ld h,0ffh		;0307	26 ff		& .
	push hl			;0309	e5		.
	ld hl,l0000h		;030a	21 00 00	! . .
	push hl			;030d	e5		.
	push hl			;030e	e5		.
	exx			;030f	d9		.
	call sub_0f99h		;0310	cd 99 0f	. . .
	pop ix			;0313	dd e1		. .
	bit 7,(iy+001h)		;0315	fd cb 01 7e	. . . ~
	ret z			;0319	c8		.
	ld (ix+00bh),000h	;031a	dd 36 0b 00	. 6 . .
	ld (ix+00ch),01bh	;031e	dd 36 0c 1b	. 6 . .
	ld hl,04000h		;0322	21 00 40	! . @
	ld (ix+00dh),l		;0325	dd 75 0d	. u .
	ld (ix+00eh),h		;0328	dd 74 0e	. t .
	jp l0440h		;032b	c3 40 04	. @ .
l032eh:
	cp 0afh			;032e	fe af		. .
	jp nz,l0447h		;0330	c2 47 04	. G .
	ld a,(05c74h)		;0333	3a 74 5c	: t \
	cp 003h			;0336	fe 03		. .
	jp z,l08d9h		;0338	ca d9 08	. . .
	push ix			;033b	dd e5		. .
	exx			;033d	d9		.
	ld hl,l0020h		;033e	21 20 00	!   .
	push hl			;0341	e5		.
	ld l,000h		;0342	2e 00		. .
	ld h,0ffh		;0344	26 ff		& .
	push hl			;0346	e5		.
	ld hl,l0000h		;0347	21 00 00	! . .
	push hl			;034a	e5		.
	push hl			;034b	e5		.
	exx			;034c	d9		.
	call sub_0f99h		;034d	cd 99 0f	. . .
	exx			;0350	d9		.
	ld hl,021e7h		;0351	21 e7 21	! . !
	push hl			;0354	e5		.
	ld l,000h		;0355	2e 00		. .
	ld h,0ffh		;0357	26 ff		& .
	push hl			;0359	e5		.
	ld hl,l0000h		;035a	21 00 00	! . .
	push hl			;035d	e5		.
	push hl			;035e	e5		.
	exx			;035f	d9		.
	call sub_0f99h		;0360	cd 99 0f	. . .
	pop ix			;0363	dd e1		. .
	jr nz,l0387h		;0365	20 20		   
	ld a,(05c74h)		;0367	3a 74 5c	: t \
	and a			;036a	a7		.
	jp z,l08d9h		;036b	ca d9 08	. . .
	push ix			;036e	dd e5		. .
	exx			;0370	d9		.
	ld hl,l1c51h		;0371	21 51 1c	! Q .
	push hl			;0374	e5		.
	ld l,000h		;0375	2e 00		. .
	ld h,0ffh		;0377	26 ff		& .
	push hl			;0379	e5		.
	ld hl,l0000h		;037a	21 00 00	! . .
	push hl			;037d	e5		.
	push hl			;037e	e5		.
	exx			;037f	d9		.
	call sub_0f99h		;0380	cd 99 0f	. . .
	pop ix			;0383	dd e1		. .
	jr l03bch		;0385	18 35		. 5
l0387h:
	push ix			;0387	dd e5		. .
	exx			;0389	d9		.
	ld hl,l1be5h		;038a	21 e5 1b	! . .
	push hl			;038d	e5		.
	ld l,000h		;038e	2e 00		. .
	ld h,0ffh		;0390	26 ff		& .
	push hl			;0392	e5		.
	ld hl,l0000h		;0393	21 00 00	! . .
	push hl			;0396	e5		.
	push hl			;0397	e5		.
	exx			;0398	d9		.
	call sub_0f99h		;0399	cd 99 0f	. . .
	exx			;039c	d9		.
	ld hl,l0017h+1		;039d	21 18 00	! . .
	push hl			;03a0	e5		.
	ld l,000h		;03a1	2e 00		. .
	ld h,0ffh		;03a3	26 ff		& .
	push hl			;03a5	e5		.
	ld hl,l0000h		;03a6	21 00 00	! . .
	push hl			;03a9	e5		.
	push hl			;03aa	e5		.
	exx			;03ab	d9		.
	call sub_0f99h		;03ac	cd 99 0f	. . .
	pop ix			;03af	dd e1		. .
	cp 02ch			;03b1	fe 2c		. ,
	jr z,l03d5h		;03b3	28 20		(  
	ld a,(05c74h)		;03b5	3a 74 5c	: t \
	and a			;03b8	a7		.
	jp z,l08d9h		;03b9	ca d9 08	. . .
l03bch:
	push ix			;03bc	dd e5		. .
	exx			;03be	d9		.
	ld hl,l1c51h		;03bf	21 51 1c	! Q .
	push hl			;03c2	e5		.
	ld l,000h		;03c3	2e 00		. .
	ld h,0ffh		;03c5	26 ff		& .
	push hl			;03c7	e5		.
	ld hl,l0000h		;03c8	21 00 00	! . .
	push hl			;03cb	e5		.
	push hl			;03cc	e5		.
	exx			;03cd	d9		.
	call sub_0f99h		;03ce	cd 99 0f	. . .
	pop ix			;03d1	dd e1		. .
	jr l03ffh		;03d3	18 2a		. *
l03d5h:
	push ix			;03d5	dd e5		. .
	exx			;03d7	d9		.
	ld hl,l0020h		;03d8	21 20 00	!   .
	push hl			;03db	e5		.
	ld l,000h		;03dc	2e 00		. .
	ld h,0ffh		;03de	26 ff		& .
	push hl			;03e0	e5		.
	ld hl,l0000h		;03e1	21 00 00	! . .
	push hl			;03e4	e5		.
	push hl			;03e5	e5		.
	exx			;03e6	d9		.
	call sub_0f99h		;03e7	cd 99 0f	. . .
	exx			;03ea	d9		.
	ld hl,l1be5h		;03eb	21 e5 1b	! . .
	push hl			;03ee	e5		.
	ld l,000h		;03ef	2e 00		. .
	ld h,0ffh		;03f1	26 ff		& .
	push hl			;03f3	e5		.
	ld hl,l0000h		;03f4	21 00 00	! . .
	push hl			;03f7	e5		.
	push hl			;03f8	e5		.
	exx			;03f9	d9		.
	call sub_0f99h		;03fa	cd 99 0f	. . .
	pop ix			;03fd	dd e1		. .
l03ffh:
	bit 7,(iy+001h)		;03ff	fd cb 01 7e	. . . ~
	ret z			;0403	c8		.
	push ix			;0404	dd e5		. .
	exx			;0406	d9		.
	ld hl,l1f23h		;0407	21 23 1f	! # .
	push hl			;040a	e5		.
	ld l,000h		;040b	2e 00		. .
	ld h,0ffh		;040d	26 ff		& .
	push hl			;040f	e5		.
	ld hl,l0000h		;0410	21 00 00	! . .
	push hl			;0413	e5		.
	push hl			;0414	e5		.
l0415h:
	exx			;0415	d9		.
	call sub_0f99h		;0416	cd 99 0f	. . .
	pop ix			;0419	dd e1		. .
	ld (ix+00bh),c		;041b	dd 71 0b	. q .
	ld (ix+00ch),b		;041e	dd 70 0c	. p .
	push ix			;0421	dd e5		. .
	exx			;0423	d9		.
	ld hl,l1f23h		;0424	21 23 1f	! # .
	push hl			;0427	e5		.
	ld l,000h		;0428	2e 00		. .
	ld h,0ffh		;042a	26 ff		& .
	push hl			;042c	e5		.
	ld hl,l0000h		;042d	21 00 00	! . .
	push hl			;0430	e5		.
	push hl			;0431	e5		.
	exx			;0432	d9		.
	call sub_0f99h		;0433	cd 99 0f	. . .
	pop ix			;0436	dd e1		. .
	ld (ix+00dh),c		;0438	dd 71 0d	. q .
	ld (ix+00eh),b		;043b	dd 70 0e	. p .
	ld h,b			;043e	60		`
	ld l,c			;043f	69		i
l0440h:
	ld (ix+000h),003h	;0440	dd 36 00 03	. 6 . .
	jp l04c9h		;0444	c3 c9 04	. . .
l0447h:
	cp 0cah			;0447	fe ca		. .
	jr z,l0456h		;0449	28 0b		( .
	bit 7,(iy+001h)		;044b	fd cb 01 7e	. . . ~
	ret z			;044f	c8		.
	ld (ix+00eh),080h	;0450	dd 36 0e 80	. 6 . .
	jr l04a9h		;0454	18 53		. S
l0456h:
	ld a,(05c74h)		;0456	3a 74 5c	: t \
	and a			;0459	a7		.
	jp nz,l08d9h		;045a	c2 d9 08	. . .
	push ix			;045d	dd e5		. .
	exx			;045f	d9		.
	ld hl,l0020h		;0460	21 20 00	!   .
	push hl			;0463	e5		.
	ld l,000h		;0464	2e 00		. .
	ld h,0ffh		;0466	26 ff		& .
	push hl			;0468	e5		.
	ld hl,l0000h		;0469	21 00 00	! . .
	push hl			;046c	e5		.
	push hl			;046d	e5		.
	exx			;046e	d9		.
	call sub_0f99h		;046f	cd 99 0f	. . .
	exx			;0472	d9		.
	ld hl,l1be5h		;0473	21 e5 1b	! . .
	push hl			;0476	e5		.
	ld l,000h		;0477	2e 00		. .
	ld h,0ffh		;0479	26 ff		& .
	push hl			;047b	e5		.
	ld hl,l0000h		;047c	21 00 00	! . .
	push hl			;047f	e5		.
	push hl			;0480	e5		.
	exx			;0481	d9		.
	call sub_0f99h		;0482	cd 99 0f	. . .
	pop ix			;0485	dd e1		. .
	bit 7,(iy+001h)		;0487	fd cb 01 7e	. . . ~
	ret z			;048b	c8		.
	push ix			;048c	dd e5		. .
	exx			;048e	d9		.
	ld hl,l1f23h		;048f	21 23 1f	! # .
	push hl			;0492	e5		.
	ld l,000h		;0493	2e 00		. .
	ld h,0ffh		;0495	26 ff		& .
	push hl			;0497	e5		.
	ld hl,l0000h		;0498	21 00 00	! . .
	push hl			;049b	e5		.
	push hl			;049c	e5		.
	exx			;049d	d9		.
	call sub_0f99h		;049e	cd 99 0f	. . .
	pop ix			;04a1	dd e1		. .
	ld (ix+00dh),c		;04a3	dd 71 0d	. q .
	ld (ix+00eh),b		;04a6	dd 70 0e	. p .
l04a9h:
	ld (ix+000h),000h	;04a9	dd 36 00 00	. 6 . .
	ld hl,(05c59h)		;04ad	2a 59 5c	* Y \
	ld de,(05c53h)		;04b0	ed 5b 53 5c	. [ S \
	scf			;04b4	37		7
	sbc hl,de		;04b5	ed 52		. R
	ld (ix+00bh),l		;04b7	dd 75 0b	. u .
	ld (ix+00ch),h		;04ba	dd 74 0c	. t .
	ld hl,(05c4bh)		;04bd	2a 4b 5c	* K \
	sbc hl,de		;04c0	ed 52		. R
	ld (ix+00fh),l		;04c2	dd 75 0f	. u .
	ld (ix+010h),h		;04c5	dd 74 10	. t .
	ex de,hl		;04c8	eb		.
l04c9h:
	ld a,(05c74h)		;04c9	3a 74 5c	: t \
	and a			;04cc	a7		.
	jp z,l0851h		;04cd	ca 51 08	. Q .
	push hl			;04d0	e5		.
	ld bc,l0010h+1		;04d1	01 11 00	. . .
	add ix,bc		;04d4	dd 09		. .
l04d6h:
	push ix			;04d6	dd e5		. .
	ld de,l0010h+1		;04d8	11 11 00	. . .
	xor a			;04db	af		.
	scf			;04dc	37		7
	call sub_00fch		;04dd	cd fc 00	. . .
	pop ix			;04e0	dd e1		. .
	jr nc,l04d6h		;04e2	30 f2		0 .
	ld a,0feh		;04e4	3e fe		> .
	push ix			;04e6	dd e5		. .
	exx			;04e8	d9		.
	ld hl,l1230h		;04e9	21 30 12	! 0 .
	push hl			;04ec	e5		.
	ld l,000h		;04ed	2e 00		. .
	ld h,0ffh		;04ef	26 ff		& .
	push hl			;04f1	e5		.
	ld hl,l0000h		;04f2	21 00 00	! . .
	push hl			;04f5	e5		.
	push hl			;04f6	e5		.
	exx			;04f7	d9		.
	call sub_0f99h		;04f8	cd 99 0f	. . .
	pop ix			;04fb	dd e1		. .
	ld (iy+052h),003h	;04fd	fd 36 52 03	. 6 R .
	ld c,080h		;0501	0e 80		. .
	ld a,(ix+000h)		;0503	dd 7e 00	. ~ .
	cp (ix-011h)		;0506	dd be ef	. . .
	jr nz,l050dh		;0509	20 02		  .
	ld c,0f6h		;050b	0e f6		. .
l050dh:
	cp 004h			;050d	fe 04		. .
	jr nc,l04d6h		;050f	30 c5		0 .
	ld de,03ca8h		;0511	11 a8 3c	. . <
	push bc			;0514	c5		.
	push ix			;0515	dd e5		. .
	exx			;0517	d9		.
	ld hl,l073fh		;0518	21 3f 07	! ? .
	push hl			;051b	e5		.
	ld l,000h		;051c	2e 00		. .
	ld h,0ffh		;051e	26 ff		& .
	push hl			;0520	e5		.
	ld hl,l0000h		;0521	21 00 00	! . .
	push hl			;0524	e5		.
	push hl			;0525	e5		.
	exx			;0526	d9		.
	call sub_0f99h		;0527	cd 99 0f	. . .
	pop ix			;052a	dd e1		. .
	pop bc			;052c	c1		.
	push ix			;052d	dd e5		. .
	pop de			;052f	d1		.
	ld hl,0fff0h		;0530	21 f0 ff	! . .
	add hl,de		;0533	19		.
	ld b,00ah		;0534	06 0a		. .
	ld a,(hl)		;0536	7e		~
	inc a			;0537	3c		<
	jr nz,l053dh		;0538	20 03		  .
	ld a,c			;053a	79		y
	add a,b			;053b	80		.
	ld c,a			;053c	4f		O
l053dh:
	inc de			;053d	13		.
	ld a,(de)		;053e	1a		.
	cp (hl)			;053f	be		.
	inc hl			;0540	23		#
	jr nz,l0544h		;0541	20 01		  .
	inc c			;0543	0c		.
l0544h:
	push ix			;0544	dd e5		. .
	exx			;0546	d9		.
	ld hl,l0010h		;0547	21 10 00	! . .
	push hl			;054a	e5		.
	ld l,000h		;054b	2e 00		. .
	ld h,0ffh		;054d	26 ff		& .
	push hl			;054f	e5		.
	ld hl,l0000h		;0550	21 00 00	! . .
	push hl			;0553	e5		.
	push hl			;0554	e5		.
	exx			;0555	d9		.
	call sub_0f99h		;0556	cd 99 0f	. . .
	pop ix			;0559	dd e1		. .
	djnz l053dh		;055b	10 e0		. .
	bit 7,c			;055d	cb 79		. y
	jp nz,l04d6h		;055f	c2 d6 04	. . .
	ld a,00dh		;0562	3e 0d		> .
	push ix			;0564	dd e5		. .
	exx			;0566	d9		.
	ld hl,l0010h		;0567	21 10 00	! . .
	push hl			;056a	e5		.
	ld l,000h		;056b	2e 00		. .
	ld h,0ffh		;056d	26 ff		& .
	push hl			;056f	e5		.
	ld hl,l0000h		;0570	21 00 00	! . .
	push hl			;0573	e5		.
	push hl			;0574	e5		.
	exx			;0575	d9		.
	call sub_0f99h		;0576	cd 99 0f	. . .
	pop ix			;0579	dd e1		. .
	pop hl			;057b	e1		.
	ld a,(ix+000h)		;057c	dd 7e 00	. ~ .
	cp 003h			;057f	fe 03		. .
	jr z,l058fh		;0581	28 0c		( .
	ld a,(05c74h)		;0583	3a 74 5c	: t \
	dec a			;0586	3d		=
	jp z,l05cch		;0587	ca cc 05	. . .
	cp 002h			;058a	fe 02		. .
	jp z,l06e5h		;058c	ca e5 06	. . .
l058fh:
	push hl			;058f	e5		.
	ld l,(ix-006h)		;0590	dd 6e fa	. n .
	ld h,(ix-005h)		;0593	dd 66 fb	. f .
	ld e,(ix+00bh)		;0596	dd 5e 0b	. ^ .
	ld d,(ix+00ch)		;0599	dd 56 0c	. V .
	ld a,h			;059c	7c		|
	or l			;059d	b5		.
	jr z,l05adh		;059e	28 0d		( .
	sbc hl,de		;05a0	ed 52		. R
	jr c,l05cah		;05a2	38 26		8 &
	jr z,l05adh		;05a4	28 07		( .
	ld a,(ix+000h)		;05a6	dd 7e 00	. ~ .
	cp 003h			;05a9	fe 03		. .
	jr nz,l05cah		;05ab	20 1d		  .
l05adh:
	pop hl			;05ad	e1		.
	ld a,h			;05ae	7c		|
	or l			;05af	b5		.
	jr nz,l05b8h		;05b0	20 06		  .
	ld l,(ix+00dh)		;05b2	dd 6e 0d	. n .
	ld h,(ix+00eh)		;05b5	dd 66 0e	. f .
l05b8h:
	push hl			;05b8	e5		.
	pop ix			;05b9	dd e1		. .
	ld a,(05c74h)		;05bb	3a 74 5c	: t \
	cp 002h			;05be	fe 02		. .
	scf			;05c0	37		7
	jr nz,l05c4h		;05c1	20 01		  .
	and a			;05c3	a7		.
l05c4h:
	ld a,0ffh		;05c4	3e ff		> .
l05c6h:
	call sub_00fch		;05c6	cd fc 00	. . .
	ret c			;05c9	d8		.
l05cah:
	rst 8			;05ca	cf		.
	ld a,(de)		;05cb	1a		.
l05cch:
	ld e,(ix+00bh)		;05cc	dd 5e 0b	. ^ .
	ld d,(ix+00ch)		;05cf	dd 56 0c	. V .
	push hl			;05d2	e5		.
	ld a,h			;05d3	7c		|
	or l			;05d4	b5		.
	jr nz,l05ddh		;05d5	20 06		  .
	inc de			;05d7	13		.
	inc de			;05d8	13		.
	inc de			;05d9	13		.
	ex de,hl		;05da	eb		.
	jr l05e9h		;05db	18 0c		. .
l05ddh:
	ld l,(ix-006h)		;05dd	dd 6e fa	. n .
	ld h,(ix-005h)		;05e0	dd 66 fb	. f .
	ex de,hl		;05e3	eb		.
	scf			;05e4	37		7
	sbc hl,de		;05e5	ed 52		. R
	jr c,l0606h		;05e7	38 1d		8 .
l05e9h:
	ld de,l0005h		;05e9	11 05 00	. . .
	add hl,de		;05ec	19		.
	ld b,h			;05ed	44		D
	ld c,l			;05ee	4d		M
	push ix			;05ef	dd e5		. .
	exx			;05f1	d9		.
	ld hl,01fbbh		;05f2	21 bb 1f	! . .
	push hl			;05f5	e5		.
	ld l,000h		;05f6	2e 00		. .
	ld h,0ffh		;05f8	26 ff		& .
	push hl			;05fa	e5		.
	ld hl,l0000h		;05fb	21 00 00	! . .
	push hl			;05fe	e5		.
	push hl			;05ff	e5		.
	exx			;0600	d9		.
	call sub_0f99h		;0601	cd 99 0f	. . .
	pop ix			;0604	dd e1		. .
l0606h:
	pop hl			;0606	e1		.
	ld a,(ix+000h)		;0607	dd 7e 00	. ~ .
	and a			;060a	a7		.
	jr z,l0673h		;060b	28 66		( f
	ld a,h			;060d	7c		|
	or l			;060e	b5		.
	jr z,l0638h		;060f	28 27		( '
	dec hl			;0611	2b		+
	ld b,(hl)		;0612	46		F
	dec hl			;0613	2b		+
	ld c,(hl)		;0614	4e		N
	dec hl			;0615	2b		+
	inc bc			;0616	03		.
	inc bc			;0617	03		.
	inc bc			;0618	03		.
	ld (05c5fh),ix		;0619	dd 22 5f 5c	. " _ \
	push ix			;061d	dd e5		. .
	exx			;061f	d9		.
	ld hl,l1750h		;0620	21 50 17	! P .
	push hl			;0623	e5		.
	ld l,000h		;0624	2e 00		. .
	ld h,0ffh		;0626	26 ff		& .
	push hl			;0628	e5		.
	ld hl,l0000h		;0629	21 00 00	! . .
	push hl			;062c	e5		.
	push hl			;062d	e5		.
	exx			;062e	d9		.
	call sub_0f99h		;062f	cd 99 0f	. . .
	pop ix			;0632	dd e1		. .
	ld ix,(05c5fh)		;0634	dd 2a 5f 5c	. * _ \
l0638h:
	ld hl,(05c59h)		;0638	2a 59 5c	* Y \
	dec hl			;063b	2b		+
	ld c,(ix+00bh)		;063c	dd 4e 0b	. N .
	ld b,(ix+00ch)		;063f	dd 46 0c	. F .
	push bc			;0642	c5		.
	inc bc			;0643	03		.
	inc bc			;0644	03		.
	inc bc			;0645	03		.
	ld a,(ix-003h)		;0646	dd 7e fd	. ~ .
	push af			;0649	f5		.
	push ix			;064a	dd e5		. .
	exx			;064c	d9		.
	ld hl,012bbh		;064d	21 bb 12	! . .
	push hl			;0650	e5		.
	ld l,000h		;0651	2e 00		. .
	ld h,0ffh		;0653	26 ff		& .
	push hl			;0655	e5		.
	ld hl,l0000h		;0656	21 00 00	! . .
	push hl			;0659	e5		.
	push hl			;065a	e5		.
	exx			;065b	d9		.
	call sub_0f99h		;065c	cd 99 0f	. . .
	pop ix			;065f	dd e1		. .
	inc hl			;0661	23		#
	pop af			;0662	f1		.
	ld (hl),a		;0663	77		w
	pop de			;0664	d1		.
	inc hl			;0665	23		#
	ld (hl),e		;0666	73		s
	inc hl			;0667	23		#
	ld (hl),d		;0668	72		r
	inc hl			;0669	23		#
	push hl			;066a	e5		.
	pop ix			;066b	dd e1		. .
	scf			;066d	37		7
	ld a,0ffh		;066e	3e ff		> .
	jp l05c6h		;0670	c3 c6 05	. . .
l0673h:
	ex de,hl		;0673	eb		.
	ld hl,(05c59h)		;0674	2a 59 5c	* Y \
	dec hl			;0677	2b		+
	ld (05c5fh),ix		;0678	dd 22 5f 5c	. " _ \
	ld c,(ix+00bh)		;067c	dd 4e 0b	. N .
	ld b,(ix+00ch)		;067f	dd 46 0c	. F .
	push bc			;0682	c5		.
	push ix			;0683	dd e5		. .
	exx			;0685	d9		.
	ld hl,l174dh		;0686	21 4d 17	! M .
	push hl			;0689	e5		.
	ld l,000h		;068a	2e 00		. .
	ld h,0ffh		;068c	26 ff		& .
	push hl			;068e	e5		.
	ld hl,l0000h		;068f	21 00 00	! . .
	push hl			;0692	e5		.
	push hl			;0693	e5		.
	exx			;0694	d9		.
	call sub_0f99h		;0695	cd 99 0f	. . .
	pop ix			;0698	dd e1		. .
	pop bc			;069a	c1		.
	push hl			;069b	e5		.
	push bc			;069c	c5		.
	push ix			;069d	dd e5		. .
	exx			;069f	d9		.
	ld hl,012bbh		;06a0	21 bb 12	! . .
	push hl			;06a3	e5		.
	ld l,000h		;06a4	2e 00		. .
	ld h,0ffh		;06a6	26 ff		& .
	push hl			;06a8	e5		.
	ld hl,l0000h		;06a9	21 00 00	! . .
	push hl			;06ac	e5		.
	push hl			;06ad	e5		.
	exx			;06ae	d9		.
	call sub_0f99h		;06af	cd 99 0f	. . .
	pop ix			;06b2	dd e1		. .
	ld ix,(05c5fh)		;06b4	dd 2a 5f 5c	. * _ \
	inc hl			;06b8	23		#
	ld c,(ix+00fh)		;06b9	dd 4e 0f	. N .
	ld b,(ix+010h)		;06bc	dd 46 10	. F .
	add hl,bc		;06bf	09		.
	ld (05c4bh),hl		;06c0	22 4b 5c	" K \
	ld h,(ix+00eh)		;06c3	dd 66 0e	. f .
	ld a,h			;06c6	7c		|
	and 0c0h		;06c7	e6 c0		. .
	jr nz,l06d5h		;06c9	20 0a		  .
	ld l,(ix+00dh)		;06cb	dd 6e 0d	. n .
	ld (05c42h),hl		;06ce	22 42 5c	" B \
	ld (iy+00ah),000h	;06d1	fd 36 0a 00	. 6 . .
l06d5h:
	pop de			;06d5	d1		.
	pop ix			;06d6	dd e1		. .
	scf			;06d8	37		7
	ld a,0ffh		;06d9	3e ff		> .
	ld hl,(05c53h)		;06db	2a 53 5c	* S \
	dec hl			;06de	2b		+
	ld (05c57h),hl		;06df	22 57 5c	" W \
	jp l05c6h		;06e2	c3 c6 05	. . .
l06e5h:
	ld c,(ix+00bh)		;06e5	dd 4e 0b	. N .
	ld b,(ix+00ch)		;06e8	dd 46 0c	. F .
	push bc			;06eb	c5		.
	inc bc			;06ec	03		.
	push ix			;06ed	dd e5		. .
	exx			;06ef	d9		.
	ld hl,l0030h		;06f0	21 30 00	! 0 .
	push hl			;06f3	e5		.
	ld l,000h		;06f4	2e 00		. .
	ld h,0ffh		;06f6	26 ff		& .
	push hl			;06f8	e5		.
	ld hl,l0000h		;06f9	21 00 00	! . .
	push hl			;06fc	e5		.
	push hl			;06fd	e5		.
	exx			;06fe	d9		.
	call sub_0f99h		;06ff	cd 99 0f	. . .
	pop ix			;0702	dd e1		. .
	ld (hl),080h		;0704	36 80		6 .
	ex de,hl		;0706	eb		.
	pop de			;0707	d1		.
	push hl			;0708	e5		.
	push hl			;0709	e5		.
	pop ix			;070a	dd e1		. .
	scf			;070c	37		7
	ld a,0ffh		;070d	3e ff		> .
	call l05c6h		;070f	cd c6 05	. . .
	pop hl			;0712	e1		.
	ld de,(05c53h)		;0713	ed 5b 53 5c	. [ S \
l0717h:
	ld a,(hl)		;0717	7e		~
	and 0c0h		;0718	e6 c0		. .
	jr nz,l0749h		;071a	20 2d		  -
l071ch:
	ld a,(de)		;071c	1a		.
	inc de			;071d	13		.
	cp (hl)			;071e	be		.
	inc hl			;071f	23		#
	jr nz,l0724h		;0720	20 02		  .
	ld a,(de)		;0722	1a		.
	cp (hl)			;0723	be		.
l0724h:
	dec de			;0724	1b		.
	dec hl			;0725	2b		+
	jr nc,l0744h		;0726	30 1c		0 .
	push hl			;0728	e5		.
	ex de,hl		;0729	eb		.
	push ix			;072a	dd e5		. .
	exx			;072c	d9		.
	ld hl,l1720h		;072d	21 20 17	!   .
	push hl			;0730	e5		.
	ld l,000h		;0731	2e 00		. .
	ld h,0ffh		;0733	26 ff		& .
	push hl			;0735	e5		.
	ld hl,l0000h		;0736	21 00 00	! . .
	push hl			;0739	e5		.
	push hl			;073a	e5		.
	exx			;073b	d9		.
	call sub_0f99h		;073c	cd 99 0f	. . .
l073fh:
	pop ix			;073f	dd e1		. .
	pop hl			;0741	e1		.
	jr l071ch		;0742	18 d8		. .
l0744h:
	call sub_0799h		;0744	cd 99 07	. . .
	jr l0717h		;0747	18 ce		. .
l0749h:
	ld a,(hl)		;0749	7e		~
	ld c,a			;074a	4f		O
	cp 080h			;074b	fe 80		. .
	ret z			;074d	c8		.
	push hl			;074e	e5		.
	ld hl,(05c4bh)		;074f	2a 4b 5c	* K \
l0752h:
	ld a,(hl)		;0752	7e		~
	cp 080h			;0753	fe 80		. .
	jr z,l0790h		;0755	28 39		( 9
	cp c			;0757	b9		.
	jr z,l0776h		;0758	28 1c		( .
l075ah:
	push bc			;075a	c5		.
	push ix			;075b	dd e5		. .
	exx			;075d	d9		.
	ld hl,l1720h		;075e	21 20 17	!   .
	push hl			;0761	e5		.
	ld l,000h		;0762	2e 00		. .
	ld h,0ffh		;0764	26 ff		& .
	push hl			;0766	e5		.
	ld hl,l0000h		;0767	21 00 00	! . .
	push hl			;076a	e5		.
	push hl			;076b	e5		.
	exx			;076c	d9		.
	call sub_0f99h		;076d	cd 99 0f	. . .
	pop ix			;0770	dd e1		. .
	pop bc			;0772	c1		.
	ex de,hl		;0773	eb		.
	jr l0752h		;0774	18 dc		. .
l0776h:
	and 0e0h		;0776	e6 e0		. .
	cp 0a0h			;0778	fe a0		. .
	jr nz,l078eh		;077a	20 12		  .
	pop de			;077c	d1		.
	push de			;077d	d5		.
	push hl			;077e	e5		.
l077fh:
	inc hl			;077f	23		#
	inc de			;0780	13		.
	ld a,(de)		;0781	1a		.
	cp (hl)			;0782	be		.
	jr nz,l078bh		;0783	20 06		  .
	rla			;0785	17		.
	jr nc,l077fh		;0786	30 f7		0 .
	pop hl			;0788	e1		.
	jr l078eh		;0789	18 03		. .
l078bh:
	pop hl			;078b	e1		.
	jr l075ah		;078c	18 cc		. .
l078eh:
	ld a,0ffh		;078e	3e ff		> .
l0790h:
	pop de			;0790	d1		.
	ex de,hl		;0791	eb		.
	inc a			;0792	3c		<
	scf			;0793	37		7
	call sub_0799h		;0794	cd 99 07	. . .
	jr l0749h		;0797	18 b0		. .
sub_0799h:
	jr nz,l07cfh		;0799	20 34		  4
	ex af,af'		;079b	08		.
	ld (05c5fh),hl		;079c	22 5f 5c	" _ \
	ex de,hl		;079f	eb		.
	push ix			;07a0	dd e5		. .
	exx			;07a2	d9		.
	ld hl,l1720h		;07a3	21 20 17	!   .
	push hl			;07a6	e5		.
	ld l,000h		;07a7	2e 00		. .
	ld h,0ffh		;07a9	26 ff		& .
	push hl			;07ab	e5		.
	ld hl,l0000h		;07ac	21 00 00	! . .
	push hl			;07af	e5		.
	push hl			;07b0	e5		.
	exx			;07b1	d9		.
	call sub_0f99h		;07b2	cd 99 0f	. . .
	exx			;07b5	d9		.
	ld hl,l1750h		;07b6	21 50 17	! P .
	push hl			;07b9	e5		.
	ld l,000h		;07ba	2e 00		. .
	ld h,0ffh		;07bc	26 ff		& .
	push hl			;07be	e5		.
	ld hl,l0000h		;07bf	21 00 00	! . .
	push hl			;07c2	e5		.
	push hl			;07c3	e5		.
	exx			;07c4	d9		.
	call sub_0f99h		;07c5	cd 99 0f	. . .
	pop ix			;07c8	dd e1		. .
	ex de,hl		;07ca	eb		.
	ld hl,(05c5fh)		;07cb	2a 5f 5c	* _ \
	ex af,af'		;07ce	08		.
l07cfh:
	ex af,af'		;07cf	08		.
	push de			;07d0	d5		.
	push ix			;07d1	dd e5		. .
	exx			;07d3	d9		.
	ld hl,l1720h		;07d4	21 20 17	!   .
	push hl			;07d7	e5		.
	ld l,000h		;07d8	2e 00		. .
	ld h,0ffh		;07da	26 ff		& .
	push hl			;07dc	e5		.
	ld hl,l0000h		;07dd	21 00 00	! . .
	push hl			;07e0	e5		.
	push hl			;07e1	e5		.
	exx			;07e2	d9		.
	call sub_0f99h		;07e3	cd 99 0f	. . .
	pop ix			;07e6	dd e1		. .
	ld (05c5fh),hl		;07e8	22 5f 5c	" _ \
	ld hl,(05c53h)		;07eb	2a 53 5c	* S \
	ex (sp),hl		;07ee	e3		.
	push bc			;07ef	c5		.
	ex af,af'		;07f0	08		.
	jr c,l080eh		;07f1	38 1b		8 .
	dec hl			;07f3	2b		+
	push ix			;07f4	dd e5		. .
	exx			;07f6	d9		.
	ld hl,012bbh		;07f7	21 bb 12	! . .
	push hl			;07fa	e5		.
	ld l,000h		;07fb	2e 00		. .
	ld h,0ffh		;07fd	26 ff		& .
	push hl			;07ff	e5		.
	ld hl,l0000h		;0800	21 00 00	! . .
	push hl			;0803	e5		.
	push hl			;0804	e5		.
	exx			;0805	d9		.
	call sub_0f99h		;0806	cd 99 0f	. . .
	pop ix			;0809	dd e1		. .
	inc hl			;080b	23		#
	jr l0825h		;080c	18 17		. .
l080eh:
	push ix			;080e	dd e5		. .
	exx			;0810	d9		.
	ld hl,012bbh		;0811	21 bb 12	! . .
	push hl			;0814	e5		.
	ld l,000h		;0815	2e 00		. .
	ld h,0ffh		;0817	26 ff		& .
	push hl			;0819	e5		.
	ld hl,l0000h		;081a	21 00 00	! . .
	push hl			;081d	e5		.
	push hl			;081e	e5		.
	exx			;081f	d9		.
	call sub_0f99h		;0820	cd 99 0f	. . .
	pop ix			;0823	dd e1		. .
l0825h:
	inc hl			;0825	23		#
	pop bc			;0826	c1		.
	pop de			;0827	d1		.
	ld (05c53h),de		;0828	ed 53 53 5c	. S S \
	ld de,(05c5fh)		;082c	ed 5b 5f 5c	. [ _ \
	push bc			;0830	c5		.
	push de			;0831	d5		.
	ex de,hl		;0832	eb		.
	ldir			;0833	ed b0		. .
	pop hl			;0835	e1		.
	pop bc			;0836	c1		.
	push de			;0837	d5		.
	push ix			;0838	dd e5		. .
	exx			;083a	d9		.
	ld hl,l1750h		;083b	21 50 17	! P .
	push hl			;083e	e5		.
	ld l,000h		;083f	2e 00		. .
	ld h,0ffh		;0841	26 ff		& .
	push hl			;0843	e5		.
	ld hl,l0000h		;0844	21 00 00	! . .
	push hl			;0847	e5		.
	push hl			;0848	e5		.
	exx			;0849	d9		.
	call sub_0f99h		;084a	cd 99 0f	. . .
	pop ix			;084d	dd e1		. .
	pop de			;084f	d1		.
	ret			;0850	c9		.
l0851h:
	push hl			;0851	e5		.
	ld a,0fdh		;0852	3e fd		> .
	push ix			;0854	dd e5		. .
	exx			;0856	d9		.
	ld hl,l1230h		;0857	21 30 12	! 0 .
	push hl			;085a	e5		.
	ld l,000h		;085b	2e 00		. .
	ld h,0ffh		;085d	26 ff		& .
	push hl			;085f	e5		.
	ld hl,l0000h		;0860	21 00 00	! . .
	push hl			;0863	e5		.
	push hl			;0864	e5		.
	exx			;0865	d9		.
	call sub_0f99h		;0866	cd 99 0f	. . .
	pop ix			;0869	dd e1		. .
	xor a			;086b	af		.
	ld de,03c89h		;086c	11 89 3c	. . <
	push ix			;086f	dd e5		. .
	exx			;0871	d9		.
	ld hl,l073fh		;0872	21 3f 07	! ? .
	push hl			;0875	e5		.
	ld l,000h		;0876	2e 00		. .
	ld h,0ffh		;0878	26 ff		& .
	push hl			;087a	e5		.
	ld hl,l0000h		;087b	21 00 00	! . .
	push hl			;087e	e5		.
	push hl			;087f	e5		.
	exx			;0880	d9		.
	call sub_0f99h		;0881	cd 99 0f	. . .
	pop ix			;0884	dd e1		. .
	set 5,(iy+002h)		;0886	fd cb 02 ee	. . . .
	call sub_08aah		;088a	cd aa 08	. . .
	push ix			;088d	dd e5		. .
	ld de,l0010h+1		;088f	11 11 00	. . .
	xor a			;0892	af		.
	call sub_0068h		;0893	cd 68 00	. h .
	pop ix			;0896	dd e1		. .
	ld b,032h		;0898	06 32		. 2
l089ah:
	halt			;089a	76		v
	djnz l089ah		;089b	10 fd		. .
	ld e,(ix+00bh)		;089d	dd 5e 0b	. ^ .
	ld d,(ix+00ch)		;08a0	dd 56 0c	. V .
	ld a,0ffh		;08a3	3e ff		> .
	pop ix			;08a5	dd e1		. .
	jp sub_0068h		;08a7	c3 68 00	. h .
sub_08aah:
	push af			;08aa	f5		.
	push bc			;08ab	c5		.
	push de			;08ac	d5		.
	ld bc,09c40h		;08ad	01 40 9c	. @ .
l08b0h:
	dec bc			;08b0	0b		.
	ld a,c			;08b1	79		y
	or b			;08b2	b0		.
	jr nz,l08b0h		;08b3	20 fb		  .
l08b5h:
	xor a			;08b5	af		.
	in a,(0feh)		;08b6	db fe		. .
	and 01fh		;08b8	e6 1f		. .
	cp 01fh			;08ba	fe 1f		. .
	jr z,l08b5h		;08bc	28 f7		( .
	push ix			;08be	dd e5		. .
	exx			;08c0	d9		.
	ld hl,008a9h		;08c1	21 a9 08	! . .
	push hl			;08c4	e5		.
	ld l,000h		;08c5	2e 00		. .
	ld h,0ffh		;08c7	26 ff		& .
	push hl			;08c9	e5		.
	ld hl,l0000h		;08ca	21 00 00	! . .
	push hl			;08cd	e5		.
	push hl			;08ce	e5		.
	exx			;08cf	d9		.
	call sub_0f99h		;08d0	cd 99 0f	. . .
	pop ix			;08d3	dd e1		. .
	pop de			;08d5	d1		.
	pop bc			;08d6	c1		.
	pop af			;08d7	f1		.
	ret			;08d8	c9		.
l08d9h:
	exx			;08d9	d9		.
	ld hl,l1bedh		;08da	21 ed 1b	! . .
	push hl			;08dd	e5		.
	ld l,000h		;08de	2e 00		. .
	ld h,0ffh		;08e0	26 ff		& .
	push hl			;08e2	e5		.
	exx			;08e3	d9		.
	call sub_0f8ah		;08e4	cd 8a 0f	. . .
l08e7h:
	ld hl,05eeah		;08e7	21 ea 5e	! . ^
	ld (05cbch),hl		;08ea	22 bc 5c	" . \
	call sub_09f4h		;08ed	cd f4 09	. . .
	ld hl,(05cbch)		;08f0	2a bc 5c	* . \
	ld de,l0008h		;08f3	11 08 00	. . .
	add hl,de		;08f6	19		.
	ld a,(hl)		;08f7	7e		~
	cp 001h			;08f8	fe 01		. .
	jr nz,l090fh		;08fa	20 13		  .
	push hl			;08fc	e5		.
	call sub_096ch		;08fd	cd 6c 09	. l .
	pop hl			;0900	e1		.
	inc hl			;0901	23		#
	ld e,(hl)		;0902	5e		^
	inc hl			;0903	23		#
	ld d,(hl)		;0904	56		V
	push de			;0905	d5		.
	ld b,000h		;0906	06 00		. .
	inc hl			;0908	23		#
	ld c,(hl)		;0909	4e		N
	push bc			;090a	c5		.
	ei			;090b	fb		.
	call 06572h		;090c	cd 72 65	. r e
l090fh:
	ld hl,(05cbch)		;090f	2a bc 5c	* . \
	inc hl			;0912	23		#
	ld a,(hl)		;0913	7e		~
	cp 002h			;0914	fe 02		. .
	jr z,l091eh		;0916	28 06		( .
	call sub_096ch		;0918	cd 6c 09	. l .
	jp l099ah		;091b	c3 9a 09	. . .
l091eh:
	dec hl			;091e	2b		+
	ld a,(hl)		;091f	7e		~
	cp 001h			;0920	fe 01		. .
	jr z,l0956h		;0922	28 32		( 2
	cp 002h			;0924	fe 02		. .
	jr nz,l096ah		;0926	20 42		  B
	ld de,l0006h		;0928	11 06 00	. . .
	add hl,de		;092b	19		.
	ld c,(hl)		;092c	4e		N
	inc hl			;092d	23		#
	ld b,(hl)		;092e	46		F
	ld hl,06840h		;092f	21 40 68	! @ h
	add hl,bc		;0932	09		.
	ex de,hl		;0933	eb		.
	ld hl,06840h		;0934	21 40 68	! @ h
	ldir			;0937	ed b0		. .
	call sub_0973h		;0939	cd 73 09	. s .
	ld hl,(05cbch)		;093c	2a bc 5c	* . \
	ld de,l0005h		;093f	11 05 00	. . .
	add hl,de		;0942	19		.
	ld a,(hl)		;0943	7e		~
	cp 000h			;0944	fe 00		. .
	jr z,l099ah		;0946	28 52		( R
	dec hl			;0948	2b		+
	ld c,(hl)		;0949	4e		N
	dec hl			;094a	2b		+
	ld d,(hl)		;094b	56		V
	dec hl			;094c	2b		+
	ld e,(hl)		;094d	5e		^
	push de			;094e	d5		.
	ld b,000h		;094f	06 00		. .
	push bc			;0951	c5		.
	ei			;0952	fb		.
	call 06572h		;0953	cd 72 65	. r e
l0956h:
	call sub_096ch		;0956	cd 6c 09	. l .
	ld a,080h		;0959	3e 80		> .
	ld (05cc6h),a		;095b	32 c6 5c	2 . \
	ld hl,l18c6h		;095e	21 c6 18	! . .
	push hl			;0961	e5		.
	ld b,0ffh		;0962	06 ff		. .
	ld c,000h		;0964	0e 00		. .
	push bc			;0966	c5		.
	call 06572h		;0967	cd 72 65	. r e
l096ah:
	rst 8			;096a	cf		.
	dec de			;096b	1b		.
sub_096ch:
	ld hl,06840h		;096c	21 40 68	! @ h
	ld de,00015h		;096f	11 15 00	. . .
	add hl,de		;0972	19		.
sub_0973h:
	ld (05c57h),hl		;0973	22 57 5c	" W \
	inc hl			;0976	23		#
	ld (05c53h),hl		;0977	22 53 5c	" S \
	ld (05c4bh),hl		;097a	22 4b 5c	" K \
	ld (hl),080h		;097d	36 80		6 .
	inc hl			;097f	23		#
	ld (05c59h),hl		;0980	22 59 5c	" Y \
	ld (hl),00dh		;0983	36 0d		6 .
	inc hl			;0985	23		#
	ld (hl),080h		;0986	36 80		6 .
	inc hl			;0988	23		#
	ld (05c61h),hl		;0989	22 61 5c	" a \
	ld (05c63h),hl		;098c	22 63 5c	" c \
	ld (05c65h),hl		;098f	22 65 5c	" e \
	xor a			;0992	af		.
	ld (05cc6h),a		;0993	32 c6 5c	2 . \
	ld (05cc2h),a		;0996	32 c2 5c	2 . \
	ret			;0999	c9		.
l099ah:
	ld d,0ffh		;099a	16 ff		. .
	ld e,080h		;099c	1e 80		. .
	ld hl,l0e2fh		;099e	21 2f 0e	! / .
	push hl			;09a1	e5		.
	push de			;09a2	d5		.
	ld hl,(05cbch)		;09a3	2a bc 5c	* . \
	ld de,l000bh+1		;09a6	11 0c 00	. . .
	add hl,de		;09a9	19		.
	ld b,000h		;09aa	06 00		. .
l09ach:
	ld a,(hl)		;09ac	7e		~
	cp 080h			;09ad	fe 80		. .
	jr z,l09e3h		;09af	28 32		( 2
	cp 000h			;09b1	fe 00		. .
	jr z,l09ddh		;09b3	28 28		( (
	inc hl			;09b5	23		#
	ld b,(hl)		;09b6	46		F
	ld de,00014h		;09b7	11 14 00	. . .
	add hl,de		;09ba	19		.
	ld a,(hl)		;09bb	7e		~
	rrca			;09bc	0f		.
	jr c,l09c4h		;09bd	38 05		8 .
	inc hl			;09bf	23		#
	inc hl			;09c0	23		#
	inc hl			;09c1	23		#
	jr l09ach		;09c2	18 e8		. .
l09c4h:
	inc hl			;09c4	23		#
	ld a,(hl)		;09c5	7e		~
	pop de			;09c6	d1		.
	cp e			;09c7	bb		.
	jr c,l09cfh		;09c8	38 05		8 .
	push de			;09ca	d5		.
	inc hl			;09cb	23		#
	inc hl			;09cc	23		#
	jr l09ach		;09cd	18 dd		. .
l09cfh:
	pop de			;09cf	d1		.
	ld de,l0005h		;09d0	11 05 00	. . .
	sbc hl,de		;09d3	ed 52		. R
	push hl			;09d5	e5		.
	ld c,a			;09d6	4f		O
	push bc			;09d7	c5		.
	inc de			;09d8	13		.
	inc de			;09d9	13		.
	add hl,de		;09da	19		.
	jr l09ach		;09db	18 cf		. .
l09ddh:
	ld de,l0017h+1		;09dd	11 18 00	. . .
	add hl,de		;09e0	19		.
	jr l09ach		;09e1	18 c9		. .
l09e3h:
	pop bc			;09e3	c1		.
	ld a,b			;09e4	78		x
	cp 0ffh			;09e5	fe ff		. .
	jr z,l09edh		;09e7	28 04		( .
	ld c,058h		;09e9	0e 58		. X
	jr l09efh		;09eb	18 02		. .
l09edh:
	ld c,000h		;09ed	0e 00		. .
l09efh:
	push bc			;09ef	c5		.
	ei			;09f0	fb		.
	call 06572h		;09f1	cd 72 65	. r e
sub_09f4h:
	ld hl,(05cbch)		;09f4	2a bc 5c	* . \
	xor a			;09f7	af		.
	ld (05cbeh),a		;09f8	32 be 5c	2 . \
	ld (06315h),a		;09fb	32 15 63	2 . c
	ld de,l0008h		;09fe	11 08 00	. . .
	add hl,de		;0a01	19		.
	ld e,0ffh		;0a02	1e ff		. .
	ld d,000h		;0a04	16 00		. .
	push de			;0a06	d5		.
	ld de,l0001h		;0a07	11 01 00	. . .
	push de			;0a0a	d5		.
	push hl			;0a0b	e5		.
	ld de,l0004h		;0a0c	11 04 00	. . .
	push de			;0a0f	d5		.
	ld de,l0001h		;0a10	11 01 00	. . .
	push de			;0a13	d5		.
	call 06722h		;0a14	cd 22 67	. " g
	ld a,(hl)		;0a17	7e		~
	cp 001h			;0a18	fe 01		. .
	jr z,l0a3eh		;0a1a	28 22		( "
	ld (hl),000h		;0a1c	36 00		6 .
	ld e,0ffh		;0a1e	1e ff		. .
	ld d,000h		;0a20	16 00		. .
	push de			;0a22	d5		.
	ld de,08000h		;0a23	11 00 80	. . .
	push de			;0a26	d5		.
	ld hl,(05cbch)		;0a27	2a bc 5c	* . \
	push hl			;0a2a	e5		.
	ld de,l0008h		;0a2b	11 08 00	. . .
	push de			;0a2e	d5		.
	ld de,l0001h		;0a2f	11 01 00	. . .
	push de			;0a32	d5		.
	call 06722h		;0a33	cd 22 67	. " g
	inc hl			;0a36	23		#
	ld a,(hl)		;0a37	7e		~
	cp 002h			;0a38	fe 02		. .
	jr z,l0a3eh		;0a3a	28 02		( .
	ld (hl),000h		;0a3c	36 00		6 .
l0a3eh:
	ld hl,(05cbch)		;0a3e	2a bc 5c	* . \
	ld de,l000bh+2		;0a41	11 0d 00	. . .
	add hl,de		;0a44	19		.
	ld d,0c0h		;0a45	16 c0		. .
	ld e,000h		;0a47	1e 00		. .
	call 0635ch		;0a49	cd 5c 63	. \ c
l0a4ch:
	call sub_0bd1h		;0a4c	cd d1 0b	. . .
	jp nc,l0ad4h		;0a4f	d2 d4 0a	. . .
	ld b,a			;0a52	47		G
	set 7,b			;0a53	cb f8		. .
	ld (hl),b		;0a55	70		p
	res 7,b			;0a56	cb b8		. .
	inc hl			;0a58	23		#
	ld c,0feh		;0a59	0e fe		. .
	push bc			;0a5b	c5		.
	ld de,l08e7h		;0a5c	11 e7 08	. . .
	push de			;0a5f	d5		.
	ld de,l0000h		;0a60	11 00 00	. . .
	push de			;0a63	d5		.
	ld de,l0001h		;0a64	11 01 00	. . .
	push de			;0a67	d5		.
	push de			;0a68	d5		.
	call 06722h		;0a69	cd 22 67	. " g
	ld e,0ffh		;0a6c	1e ff		. .
	ld d,a			;0a6e	57		W
	push de			;0a6f	d5		.
	ld de,l0000h		;0a70	11 00 00	. . .
	push de			;0a73	d5		.
	push hl			;0a74	e5		.
	ld de,00016h		;0a75	11 16 00	. . .
	push de			;0a78	d5		.
	ld de,l0001h		;0a79	11 01 00	. . .
	push de			;0a7c	d5		.
	call 06722h		;0a7d	cd 22 67	. " g
	ld d,(hl)		;0a80	56		V
	ld a,(l08e7h)		;0a81	3a e7 08	: . .
	cp d			;0a84	ba		.
	jp nz,l0ac2h		;0a85	c2 c2 0a	. . .
	ld c,0feh		;0a88	0e fe		. .
	push bc			;0a8a	c5		.
	ld de,l0a4ch		;0a8b	11 4c 0a	. L .
	push de			;0a8e	d5		.
	ld de,l0000h		;0a8f	11 00 00	. . .
	push de			;0a92	d5		.
	ld de,l0001h		;0a93	11 01 00	. . .
	push de			;0a96	d5		.
	push de			;0a97	d5		.
	call 06722h		;0a98	cd 22 67	. " g
	ld e,0ffh		;0a9b	1e ff		. .
	ld d,a			;0a9d	57		W
	push de			;0a9e	d5		.
	ld de,l0000h		;0a9f	11 00 00	. . .
	push de			;0aa2	d5		.
	push hl			;0aa3	e5		.
	ld de,00016h		;0aa4	11 16 00	. . .
	push de			;0aa7	d5		.
	ld de,l0001h		;0aa8	11 01 00	. . .
	push de			;0aab	d5		.
	call 06722h		;0aac	cd 22 67	. " g
	ld d,(hl)		;0aaf	56		V
	ld a,(l08e7h)		;0ab0	3a e7 08	: . .
	cp d			;0ab3	ba		.
	jp nz,l0ac2h		;0ab4	c2 c2 0a	. . .
	dec hl			;0ab7	2b		+
	dec hl			;0ab8	2b		+
	call sub_0adbh		;0ab9	cd db 0a	. . .
	ld de,00015h		;0abc	11 15 00	. . .
	add hl,de		;0abf	19		.
	jr l0acah		;0ac0	18 08		. .
l0ac2h:
	ld a,d			;0ac2	7a		z
	and 0dfh		;0ac3	e6 df		. .
	ld (hl),a		;0ac5	77		w
	dec hl			;0ac6	2b		+
	call sub_0c1fh		;0ac7	cd 1f 0c	. . .
l0acah:
	ld d,0c0h		;0aca	16 c0		. .
	ld e,001h		;0acc	1e 01		. .
	call 0635ch		;0ace	cd 5c 63	. \ c
	jp l0a4ch		;0ad1	c3 4c 0a	. L .
l0ad4h:
	dec hl			;0ad4	2b		+
	ld (hl),080h		;0ad5	36 80		6 .
	call sub_0cfbh		;0ad7	cd fb 0c	. . .
	ret			;0ada	c9		.
sub_0adbh:
	ld (hl),002h		;0adb	36 02		6 .
	push bc			;0add	c5		.
	ld de,l0038h		;0ade	11 38 00	. 8 .
	push de			;0ae1	d5		.
	push de			;0ae2	d5		.
	ld de,l0010h		;0ae3	11 10 00	. . .
	push de			;0ae6	d5		.
	ld de,l0001h		;0ae7	11 01 00	. . .
	push de			;0aea	d5		.
	call 06722h		;0aeb	cd 22 67	. " g
	inc hl			;0aee	23		#
	inc hl			;0aef	23		#
	ld a,(hl)		;0af0	7e		~
	set 0,a			;0af1	cb c7		. .
	ld (hl),a		;0af3	77		w
	ld de,l0000h		;0af4	11 00 00	. . .
	ld a,001h		;0af7	3e 01		> .
l0af9h:
	ex af,af'		;0af9	08		.
	push hl			;0afa	e5		.
	ex de,hl		;0afb	eb		.
	ld de,02000h		;0afc	11 00 20	. .  
	add hl,de		;0aff	19		.
	ex de,hl		;0b00	eb		.
	pop hl			;0b01	e1		.
	ld b,0feh		;0b02	06 fe		. .
	ld a,(05cbeh)		;0b04	3a be 5c	: . \
	ld c,a			;0b07	4f		O
	push bc			;0b08	c5		.
	ld bc,l08e7h		;0b09	01 e7 08	. . .
	push bc			;0b0c	c5		.
	push de			;0b0d	d5		.
	ld bc,l0001h		;0b0e	01 01 00	. . .
	push bc			;0b11	c5		.
	push bc			;0b12	c5		.
	call 06722h		;0b13	cd 22 67	. " g
	ld a,(05cbeh)		;0b16	3a be 5c	: . \
	ld b,a			;0b19	47		G
	ld c,000h		;0b1a	0e 00		. .
	push bc			;0b1c	c5		.
	push de			;0b1d	d5		.
	inc hl			;0b1e	23		#
	push hl			;0b1f	e5		.
	ld bc,l0001h		;0b20	01 01 00	. . .
	push bc			;0b23	c5		.
	push bc			;0b24	c5		.
	call 06722h		;0b25	cd 22 67	. " g
	ld b,(hl)		;0b28	46		F
	dec hl			;0b29	2b		+
	ld a,(l08e7h)		;0b2a	3a e7 08	: . .
	cp b			;0b2d	b8		.
	jr nz,l0b95h		;0b2e	20 65		  e
	ld b,0feh		;0b30	06 fe		. .
	ld a,(05cbeh)		;0b32	3a be 5c	: . \
	ld c,a			;0b35	4f		O
	push bc			;0b36	c5		.
	ld bc,l0a4ch		;0b37	01 4c 0a	. L .
	push bc			;0b3a	c5		.
	push de			;0b3b	d5		.
	ld bc,l0001h		;0b3c	01 01 00	. . .
	push bc			;0b3f	c5		.
	push bc			;0b40	c5		.
	call 06722h		;0b41	cd 22 67	. " g
	ld a,(05cbeh)		;0b44	3a be 5c	: . \
	ld b,a			;0b47	47		G
	ld c,000h		;0b48	0e 00		. .
	push bc			;0b4a	c5		.
	push de			;0b4b	d5		.
	inc hl			;0b4c	23		#
	push hl			;0b4d	e5		.
	ld bc,l0001h		;0b4e	01 01 00	. . .
	push bc			;0b51	c5		.
	push bc			;0b52	c5		.
	call 06722h		;0b53	cd 22 67	. " g
	ld b,(hl)		;0b56	46		F
	dec hl			;0b57	2b		+
	ld a,(l0a4ch)		;0b58	3a 4c 0a	: L .
	cp b			;0b5b	b8		.
	jr nz,l0b95h		;0b5c	20 37		  7
	ex af,af'		;0b5e	08		.
	ld b,(hl)		;0b5f	46		F
	cp 001h			;0b60	fe 01		. .
	jr nz,l0b68h		;0b62	20 04		  .
	set 1,b			;0b64	cb c8		. .
	jr l0b92h		;0b66	18 2a		. *
l0b68h:
	cp 002h			;0b68	fe 02		. .
	jr nz,l0b70h		;0b6a	20 04		  .
	set 2,b			;0b6c	cb d0		. .
	jr l0b92h		;0b6e	18 22		. "
l0b70h:
	cp 003h			;0b70	fe 03		. .
	jr nz,l0b78h		;0b72	20 04		  .
	set 3,b			;0b74	cb d8		. .
	jr l0b92h		;0b76	18 1a		. .
l0b78h:
	cp 004h			;0b78	fe 04		. .
	jr nz,l0b80h		;0b7a	20 04		  .
	set 4,b			;0b7c	cb e0		. .
	jr l0b92h		;0b7e	18 12		. .
l0b80h:
	cp 005h			;0b80	fe 05		. .
	jr nz,l0b88h		;0b82	20 04		  .
	set 5,b			;0b84	cb e8		. .
	jr l0b92h		;0b86	18 0a		. .
l0b88h:
	cp 006h			;0b88	fe 06		. .
	jr nz,l0b90h		;0b8a	20 04		  .
	set 6,b			;0b8c	cb f0		. .
	jr l0b92h		;0b8e	18 02		. .
l0b90h:
	set 7,b			;0b90	cb f8		. .
l0b92h:
	ld (hl),b		;0b92	70		p
	jr l0bcah		;0b93	18 35		. 5
l0b95h:
	ex af,af'		;0b95	08		.
	ld b,(hl)		;0b96	46		F
	cp 001h			;0b97	fe 01		. .
	jr nz,l0b9fh		;0b99	20 04		  .
	res 1,b			;0b9b	cb 88		. .
	jr l0bc9h		;0b9d	18 2a		. *
l0b9fh:
	cp 002h			;0b9f	fe 02		. .
	jr nz,l0ba7h		;0ba1	20 04		  .
	res 2,b			;0ba3	cb 90		. .
	jr l0bc9h		;0ba5	18 22		. "
l0ba7h:
	cp 003h			;0ba7	fe 03		. .
	jr nz,l0bafh		;0ba9	20 04		  .
	res 3,b			;0bab	cb 98		. .
	jr l0bc9h		;0bad	18 1a		. .
l0bafh:
	cp 004h			;0baf	fe 04		. .
	jr nz,l0bb7h		;0bb1	20 04		  .
	res 4,b			;0bb3	cb a0		. .
	jr l0bc9h		;0bb5	18 12		. .
l0bb7h:
	cp 005h			;0bb7	fe 05		. .
	jr nz,l0bbfh		;0bb9	20 04		  .
	res 5,b			;0bbb	cb a8		. .
	jr l0bc9h		;0bbd	18 0a		. .
l0bbfh:
	cp 006h			;0bbf	fe 06		. .
	jr nz,l0bc7h		;0bc1	20 04		  .
	res 6,b			;0bc3	cb b0		. .
	jr l0bc9h		;0bc5	18 02		. .
l0bc7h:
	res 7,b			;0bc7	cb b8		. .
l0bc9h:
	ld (hl),b		;0bc9	70		p
l0bcah:
	inc a			;0bca	3c		<
	cp 008h			;0bcb	fe 08		. .
	jp nz,l0af9h		;0bcd	c2 f9 0a	. . .
	ret			;0bd0	c9		.
sub_0bd1h:
	ld a,(05cbeh)		;0bd1	3a be 5c	: . \
	inc a			;0bd4	3c		<
	ld (05cbeh),a		;0bd5	32 be 5c	2 . \
	ld (06315h),a		;0bd8	32 15 63	2 . c
	ld d,0a0h		;0bdb	16 a0		. .
	ld e,a			;0bdd	5f		_
	call 0635ch		;0bde	cd 5c 63	. \ c
	ld d,080h		;0be1	16 80		. .
	ld e,a			;0be3	5f		_
	call 0635ch		;0be4	cd 5c 63	. \ c
	ld d,040h		;0be7	16 40		. @
	ld e,000h		;0be9	1e 00		. .
	call 0635ch		;0beb	cd 5c 63	. \ c
	push af			;0bee	f5		.
	ld a,(0a000h)		;0bef	3a 00 a0	: . .
	ex af,af'		;0bf2	08		.
	ld a,004h		;0bf3	3e 04		> .
	ld (0a000h),a		;0bf5	32 00 a0	2 . .
	ld d,0a0h		;0bf8	16 a0		. .
	ld e,0c0h		;0bfa	1e c0		. .
	call 063adh		;0bfc	cd ad 63	. . c
	bit 2,e			;0bff	cb 53		. S
	jr nz,l0c0ah		;0c01	20 07		  .
	ex af,af'		;0c03	08		.
	ld (0a000h),a		;0c04	32 00 a0	2 . .
	pop af			;0c07	f1		.
	scf			;0c08	37		7
	ret			;0c09	c9		.
l0c0ah:
	ex af,af'		;0c0a	08		.
	ld (0a000h),a		;0c0b	32 00 a0	2 . .
	pop af			;0c0e	f1		.
	dec a			;0c0f	3d		=
	ld (05cbeh),a		;0c10	32 be 5c	2 . \
	ld (06315h),a		;0c13	32 15 63	2 . c
	ld d,0c0h		;0c16	16 c0		. .
	ld e,004h		;0c18	1e 04		. .
	call 0635ch		;0c1a	cd 5c 63	. \ c
	and a			;0c1d	a7		.
	ret			;0c1e	c9		.
sub_0c1fh:
	dec hl			;0c1f	2b		+
	ld (hl),001h		;0c20	36 01		6 .
	ld de,00015h		;0c22	11 15 00	. . .
	add hl,de		;0c25	19		.
	ld a,(hl)		;0c26	7e		~
	rra			;0c27	1f		.
	jr c,l0c2fh		;0c28	38 05		8 .
	ld de,l0004h		;0c2a	11 04 00	. . .
	add hl,de		;0c2d	19		.
	ret			;0c2e	c9		.
l0c2fh:
	ld c,008h		;0c2f	0e 08		. .
	ld a,(05cbeh)		;0c31	3a be 5c	: . \
	dec hl			;0c34	2b		+
	dec hl			;0c35	2b		+
	dec hl			;0c36	2b		+
	ld d,(hl)		;0c37	56		V
	dec hl			;0c38	2b		+
	ld e,(hl)		;0c39	5e		^
	ld h,d			;0c3a	62		b
	ld l,e			;0c3b	6b		k
	ld b,a			;0c3c	47		G
	push hl			;0c3d	e5		.
	push bc			;0c3e	c5		.
	ld bc,l0000h		;0c3f	01 00 00	. . .
	push bc			;0c42	c5		.
	push bc			;0c43	c5		.
	call 065d0h		;0c44	cd d0 65	. . e
	ld de,l0008h		;0c47	11 08 00	. . .
	add hl,de		;0c4a	19		.
	ret			;0c4b	c9		.
	xor a			;0c4c	af		.
	ld (05cbeh),a		;0c4d	32 be 5c	2 . \
	ld (06315h),a		;0c50	32 15 63	2 . c
	ld d,0c0h		;0c53	16 c0		. .
	ld e,000h		;0c55	1e 00		. .
	call 0635ch		;0c57	cd 5c 63	. \ c
	ld hl,(05cbch)		;0c5a	2a bc 5c	* . \
	ld de,l000bh+1		;0c5d	11 0c 00	. . .
l0c60h:
	add hl,de		;0c60	19		.
	call sub_0bd1h		;0c61	cd d1 0b	. . .
	jp nc,l0cf5h		;0c64	d2 f5 0c	. . .
	ld a,(hl)		;0c67	7e		~
	push hl			;0c68	e5		.
	cp 080h			;0c69	fe 80		. .
	jr nz,l0c72h		;0c6b	20 05		  .
	ld de,l0017h+1		;0c6d	11 18 00	. . .
	add hl,de		;0c70	19		.
	ld (hl),a		;0c71	77		w
l0c72h:
	call sub_0bd1h		;0c72	cd d1 0b	. . .
	ld hl,05fe9h		;0c75	21 e9 5f	! . _
	ld e,0ffh		;0c78	1e ff		. .
	ld d,a			;0c7a	57		W
	push de			;0c7b	d5		.
	ld de,l0000h		;0c7c	11 00 00	. . .
	push de			;0c7f	d5		.
	push hl			;0c80	e5		.
	ld de,00016h		;0c81	11 16 00	. . .
	push de			;0c84	d5		.
	ld de,l0001h		;0c85	11 01 00	. . .
	push de			;0c88	d5		.
	call 06722h		;0c89	cd 22 67	. " g
	ex af,af'		;0c8c	08		.
	ld a,(hl)		;0c8d	7e		~
	cpl			;0c8e	2f		/
	dec hl			;0c8f	2b		+
	ld (hl),a		;0c90	77		w
	ex af,af'		;0c91	08		.
	ld d,0ffh		;0c92	16 ff		. .
	ld e,a			;0c94	5f		_
	push de			;0c95	d5		.
	push hl			;0c96	e5		.
	ld de,l0001h+1		;0c97	11 02 00	. . .
	push de			;0c9a	d5		.
	ld de,l0001h		;0c9b	11 01 00	. . .
	push de			;0c9e	d5		.
	push de			;0c9f	d5		.
	call 06722h		;0ca0	cd 22 67	. " g
	ld e,0ffh		;0ca3	1e ff		. .
	ld d,a			;0ca5	57		W
	push de			;0ca6	d5		.
	ld de,l0001h+1		;0ca7	11 02 00	. . .
	push de			;0caa	d5		.
	inc hl			;0cab	23		#
	push hl			;0cac	e5		.
	ld de,l0001h		;0cad	11 01 00	. . .
	push de			;0cb0	d5		.
	push de			;0cb1	d5		.
	call 06722h		;0cb2	cd 22 67	. " g
	ld a,(hl)		;0cb5	7e		~
	dec hl			;0cb6	2b		+
	ld b,(hl)		;0cb7	46		F
	cp b			;0cb8	b8		.
	jr nz,l0ccah		;0cb9	20 0f		  .
	pop hl			;0cbb	e1		.
	ld a,(hl)		;0cbc	7e		~
	cp 002h			;0cbd	fe 02		. .
	jr nz,l0cc5h		;0cbf	20 04		  .
	inc hl			;0cc1	23		#
	inc hl			;0cc2	23		#
	jr l0ce8h		;0cc3	18 23		. #
l0cc5h:
	call sub_0adbh		;0cc5	cd db 0a	. . .
	jr l0ce8h		;0cc8	18 1e		. .
l0ccah:
	ld c,(hl)		;0cca	4e		N
	pop hl			;0ccb	e1		.
	inc hl			;0ccc	23		#
	inc hl			;0ccd	23		#
	ld a,(hl)		;0cce	7e		~
	cp c			;0ccf	b9		.
	jr z,l0ce8h		;0cd0	28 16		( .
	push hl			;0cd2	e5		.
	ex de,hl		;0cd3	eb		.
	ld hl,05fe9h		;0cd4	21 e9 5f	! . _
	ld bc,00016h		;0cd7	01 16 00	. . .
	ldir			;0cda	ed b0		. .
	pop hl			;0cdc	e1		.
	dec hl			;0cdd	2b		+
	ld a,(05cbeh)		;0cde	3a be 5c	: . \
	set 7,a			;0ce1	cb ff		. .
	ld (hl),a		;0ce3	77		w
	call sub_0c1fh		;0ce4	cd 1f 0c	. . .
	inc hl			;0ce7	23		#
l0ce8h:
	ld d,0c0h		;0ce8	16 c0		. .
	ld e,001h		;0cea	1e 01		. .
	call 0635ch		;0cec	cd 5c 63	. \ c
	ld de,00016h		;0cef	11 16 00	. . .
	jp l0c60h		;0cf2	c3 60 0c	. ` .
l0cf5h:
	ld (hl),080h		;0cf5	36 80		6 .
	call sub_0cfbh		;0cf7	cd fb 0c	. . .
	ret			;0cfa	c9		.
sub_0cfbh:
	xor a			;0cfb	af		.
	ld (05cbeh),a		;0cfc	32 be 5c	2 . \
l0cffh:
	ld hl,(05cbch)		;0cff	2a bc 5c	* . \
	ld de,l000bh+1		;0d02	11 0c 00	. . .
	add hl,de		;0d05	19		.
l0d06h:
	ld a,(hl)		;0d06	7e		~
	cp 080h			;0d07	fe 80		. .
	jr z,l0d84h		;0d09	28 79		( y
	inc hl			;0d0b	23		#
	ld a,(hl)		;0d0c	7e		~
	bit 7,a			;0d0d	cb 7f		. .
	jr nz,l0d17h		;0d0f	20 06		  .
	ld de,l0017h		;0d11	11 17 00	. . .
	add hl,de		;0d14	19		.
	jr l0d06h		;0d15	18 ef		. .
l0d17h:
	ld (05fe9h),hl		;0d17	22 e9 5f	" . _
	dec hl			;0d1a	2b		+
	ld a,(hl)		;0d1b	7e		~
	cp 002h			;0d1c	fe 02		. .
	jr nz,l0d28h		;0d1e	20 08		  .
	ld de,l0017h		;0d20	11 17 00	. . .
	add hl,de		;0d23	19		.
	ld a,0ffh		;0d24	3e ff		> .
	jr l0d2dh		;0d26	18 05		. .
l0d28h:
	ld de,l0017h		;0d28	11 17 00	. . .
	add hl,de		;0d2b	19		.
	ld a,(hl)		;0d2c	7e		~
l0d2dh:
	ld (05febh),a		;0d2d	32 eb 5f	2 . _
l0d30h:
	inc hl			;0d30	23		#
l0d31h:
	ld a,(hl)		;0d31	7e		~
	cp 080h			;0d32	fe 80		. .
	jr z,l0d64h		;0d34	28 2e		( .
	inc hl			;0d36	23		#
	ld a,(hl)		;0d37	7e		~
	bit 7,a			;0d38	cb 7f		. .
	jr nz,l0d42h		;0d3a	20 06		  .
	ld de,l0017h		;0d3c	11 17 00	. . .
	add hl,de		;0d3f	19		.
	jr l0d30h		;0d40	18 ee		. .
l0d42h:
	dec hl			;0d42	2b		+
	ld a,(hl)		;0d43	7e		~
	cp 002h			;0d44	fe 02		. .
	jr nz,l0d4eh		;0d46	20 06		  .
	ld de,l0017h		;0d48	11 17 00	. . .
	add hl,de		;0d4b	19		.
	jr l0d30h		;0d4c	18 e2		. .
l0d4eh:
	ex de,hl		;0d4e	eb		.
	ld bc,l0017h		;0d4f	01 17 00	. . .
	add hl,bc		;0d52	09		.
	ld a,(05febh)		;0d53	3a eb 5f	: . _
	ld b,a			;0d56	47		G
	ld a,(hl)		;0d57	7e		~
	cp b			;0d58	b8		.
	jr nc,l0d30h		;0d59	30 d5		0 .
	ld (05febh),a		;0d5b	32 eb 5f	2 . _
	ld (05fe9h),de		;0d5e	ed 53 e9 5f	. S . _
	jr l0d30h		;0d62	18 cc		. .
l0d64h:
	ld a,(05cbeh)		;0d64	3a be 5c	: . \
	inc a			;0d67	3c		<
	ld (05cbeh),a		;0d68	32 be 5c	2 . \
	ld hl,(05fe9h)		;0d6b	2a e9 5f	* . _
	ld (hl),a		;0d6e	77		w
	ld e,0ffh		;0d6f	1e ff		. .
	ld d,a			;0d71	57		W
	push de			;0d72	d5		.
	ld e,(hl)		;0d73	5e		^
	ld d,000h		;0d74	16 00		. .
	push de			;0d76	d5		.
	ld e,000h		;0d77	1e 00		. .
	push de			;0d79	d5		.
	ld e,001h		;0d7a	1e 01		. .
	push de			;0d7c	d5		.
	push de			;0d7d	d5		.
	call 06722h		;0d7e	cd 22 67	. " g
	jp l0cffh		;0d81	c3 ff 0c	. . .
l0d84h:
	xor a			;0d84	af		.
	ld (05cbeh),a		;0d85	32 be 5c	2 . \
	ld (06315h),a		;0d88	32 15 63	2 . c
	ld d,0c0h		;0d8b	16 c0		. .
	ld e,000h		;0d8d	1e 00		. .
	call 0635ch		;0d8f	cd 5c 63	. \ c
	ld hl,(05cbch)		;0d92	2a bc 5c	* . \
	ld de,l000bh+2		;0d95	11 0d 00	. . .
	add hl,de		;0d98	19		.
	ld d,0a0h		;0d99	16 a0		. .
l0d9bh:
	call sub_0bd1h		;0d9b	cd d1 0b	. . .
	ret nc			;0d9e	d0		.
	ld e,(hl)		;0d9f	5e		^
	call 0635ch		;0da0	cd 5c 63	. \ c
	ld d,0c0h		;0da3	16 c0		. .
	ld e,001h		;0da5	1e 01		. .
	call 0635ch		;0da7	cd 5c 63	. \ c
	ld de,l0017h+1		;0daa	11 18 00	. . .
	add hl,de		;0dad	19		.
	jr l0d9bh		;0dae	18 eb		. .
sub_0db0h:
	push bc			;0db0	c5		.
	push de			;0db1	d5		.
	push hl			;0db2	e5		.
	push af			;0db3	f5		.
	ld hl,(05cb4h)		;0db4	2a b4 5c	* . \
	ld de,(05c7bh)		;0db7	ed 5b 7b 5c	. [ { \
	and a			;0dbb	a7		.
	sbc hl,de		;0dbc	ed 52		. R
	ld b,h			;0dbe	44		D
	ld c,l			;0dbf	4d		M
	inc bc			;0dc0	03		.
	ld hl,(05c7bh)		;0dc1	2a 7b 5c	* { \
	push hl			;0dc4	e5		.
	ld de,00840h		;0dc5	11 40 08	. @ .
	and a			;0dc8	a7		.
	sbc hl,de		;0dc9	ed 52		. R
	ex de,hl		;0dcb	eb		.
	pop hl			;0dcc	e1		.
	ld (05c7bh),de		;0dcd	ed 53 7b 5c	. S { \
	ldir			;0dd1	ed b0		. .
	ld hl,l0000h		;0dd3	21 00 00	! . .
	add hl,sp		;0dd6	39		9
	ld bc,097c0h		;0dd7	01 c0 97	. . .
	add hl,bc		;0dda	09		.
	di			;0ddb	f3		.
	ld sp,hl		;0ddc	f9		.
	ld de,0f7c0h		;0ddd	11 c0 f7	. . .
	ld hl,06000h		;0de0	21 00 60	! . `
	ld bc,00840h		;0de3	01 40 08	. @ .
	ldir			;0de6	ed b0		. .
	ld hl,l1d00h		;0de8	21 00 1d	! . .
	ld bc,097c0h		;0deb	01 c0 97	. . .
l0deeh:
	ld e,(hl)		;0dee	5e		^
	inc hl			;0def	23		#
	ld d,(hl)		;0df0	56		V
	inc hl			;0df1	23		#
	ld a,e			;0df2	7b		{
	or d			;0df3	b2		.
	jr z,l0e05h		;0df4	28 0f		( .
	ex de,hl		;0df6	eb		.
	add hl,bc		;0df7	09		.
	push de			;0df8	d5		.
	ld e,(hl)		;0df9	5e		^
	inc hl			;0dfa	23		#
	ld d,(hl)		;0dfb	56		V
	ex de,hl		;0dfc	eb		.
	add hl,bc		;0dfd	09		.
	ex de,hl		;0dfe	eb		.
	ld (hl),d		;0dff	72		r
	dec hl			;0e00	2b		+
	ld (hl),e		;0e01	73		s
	pop hl			;0e02	e1		.
	jr l0deeh		;0e03	18 e9		. .
l0e05h:
	pop af			;0e05	f1		.
	ld (05cc2h),a		;0e06	32 c2 5c	2 . \
	push af			;0e09	f5		.
	ei			;0e0a	fb		.
	ld hl,06000h		;0e0b	21 00 60	! . `
l0e0eh:
	xor a			;0e0e	af		.
	ld (hl),a		;0e0f	77		w
	inc hl			;0e10	23		#
	ld a,h			;0e11	7c		|
	cp 07bh			;0e12	fe 7b		. {
	jr nz,l0e0eh		;0e14	20 f8		  .
	pop af			;0e16	f1		.
	push af			;0e17	f5		.
	and 07fh		;0e18	e6 7f		. .
	ld b,a			;0e1a	47		G
	in a,(0ffh)		;0e1b	db ff		. .
	and 080h		;0e1d	e6 80		. .
	or b			;0e1f	b0		.
	out (0ffh),a		;0e20	d3 ff		. .
	pop hl			;0e22	e1		.
	pop de			;0e23	d1		.
	pop bc			;0e24	c1		.
	pop af			;0e25	f1		.
	ret			;0e26	c9		.
sub_0e27h:
	push af			;0e27	f5		.
	push bc			;0e28	c5		.
	push de			;0e29	d5		.
	push hl			;0e2a	e5		.
	in a,(0ffh)		;0e2b	db ff		. .
	and 080h		;0e2d	e6 80		. .
l0e2fh:
	out (0ffh),a		;0e2f	d3 ff		. .
	ld hl,l0000h		;0e31	21 00 00	! . .
	add hl,sp		;0e34	39		9
	ld de,097c0h		;0e35	11 c0 97	. . .
	and a			;0e38	a7		.
	sbc hl,de		;0e39	ed 52		. R
	di			;0e3b	f3		.
	ld sp,hl		;0e3c	f9		.
	ld hl,0ffffh		;0e3d	21 ff ff	! . .
	ld de,0683fh		;0e40	11 3f 68	. ? h
	ld bc,00840h		;0e43	01 40 08	. @ .
	lddr			;0e46	ed b8		. .
	ld hl,l1d00h		;0e48	21 00 1d	! . .
	ld bc,097c0h		;0e4b	01 c0 97	. . .
l0e4eh:
	ld e,(hl)		;0e4e	5e		^
	inc hl			;0e4f	23		#
	ld d,(hl)		;0e50	56		V
	inc hl			;0e51	23		#
	ld a,e			;0e52	7b		{
	or d			;0e53	b2		.
	jr z,l0e66h		;0e54	28 10		( .
	push hl			;0e56	e5		.
	ex de,hl		;0e57	eb		.
	ld e,(hl)		;0e58	5e		^
	inc hl			;0e59	23		#
	ld d,(hl)		;0e5a	56		V
	ex de,hl		;0e5b	eb		.
	and a			;0e5c	a7		.
	sbc hl,bc		;0e5d	ed 42		. B
	ex de,hl		;0e5f	eb		.
	ld (hl),d		;0e60	72		r
	dec hl			;0e61	2b		+
	ld (hl),e		;0e62	73		s
	pop hl			;0e63	e1		.
	jr l0e4eh		;0e64	18 e8		. .
l0e66h:
	xor a			;0e66	af		.
	ld (05cc2h),a		;0e67	32 c2 5c	2 . \
	ei			;0e6a	fb		.
	ld hl,0f7bfh		;0e6b	21 bf f7	! . .
	ld de,0ffffh		;0e6e	11 ff ff	. . .
	push hl			;0e71	e5		.
	ld bc,(05c7bh)		;0e72	ed 4b 7b 5c	. K { \
	and a			;0e76	a7		.
	sbc hl,bc		;0e77	ed 42		. B
	ld b,h			;0e79	44		D
	ld c,l			;0e7a	4d		M
	inc bc			;0e7b	03		.
	pop hl			;0e7c	e1		.
	lddr			;0e7d	ed b8		. .
	ld de,00840h		;0e7f	11 40 08	. @ .
	ld hl,(05c7bh)		;0e82	2a 7b 5c	* { \
	add hl,de		;0e85	19		.
	ld (05c7bh),hl		;0e86	22 7b 5c	" { \
	pop hl			;0e89	e1		.
	pop de			;0e8a	d1		.
	pop bc			;0e8b	c1		.
	pop af			;0e8c	f1		.
	ret			;0e8d	c9		.
	push bc			;0e8e	c5		.
	push de			;0e8f	d5		.
	push hl			;0e90	e5		.
	push af			;0e91	f5		.
	ld b,a			;0e92	47		G
	ld a,(05cc2h)		;0e93	3a c2 5c	: . \
	and a			;0e96	a7		.
	jr nz,l0eedh		;0e97	20 54		  T
	or b			;0e99	b0		.
	jp z,l0f3dh		;0e9a	ca 3d 0f	. = .
	ld hl,l12c0h		;0e9d	21 c0 12	! . .
	ld b,h			;0ea0	44		D
	ld c,l			;0ea1	4d		M
	ld de,00840h		;0ea2	11 40 08	. @ .
	add hl,de		;0ea5	19		.
	ld de,(05c65h)		;0ea6	ed 5b 65 5c	. [ e \
	add hl,de		;0eaa	19		.
	ld de,(05cb2h)		;0eab	ed 5b b2 5c	. [ . \
	and a			;0eaf	a7		.
	sbc hl,de		;0eb0	ed 52		. R
	jp nc,l0f3ah		;0eb2	d2 3a 0f	. : .
	ld hl,0683fh		;0eb5	21 3f 68	! ? h
	ld de,l12cah		;0eb8	11 ca 12	. . .
	push de			;0ebb	d5		.
	ld de,0ff00h		;0ebc	11 00 ff	. . .
	push de			;0ebf	d5		.
	ld de,l0000h		;0ec0	11 00 00	. . .
	push de			;0ec3	d5		.
	push de			;0ec4	d5		.
	call 065d0h		;0ec5	cd d0 65	. . e
	ld hl,(05c65h)		;0ec8	2a 65 5c	* e \
	ex de,hl		;0ecb	eb		.
	lddr			;0ecc	ed b8		. .
	pop af			;0ece	f1		.
	push af			;0ecf	f5		.
	call sub_0db0h		;0ed0	cd b0 0d	. . .
	ld bc,097c0h		;0ed3	01 c0 97	. . .
	ld hl,(05c3dh)		;0ed6	2a 3d 5c	* = \
	add hl,bc		;0ed9	09		.
	ld (05c3dh),hl		;0eda	22 3d 5c	" = \
	ld hl,(05c3fh)		;0edd	2a 3f 5c	* ? \
	add hl,bc		;0ee0	09		.
	ld (05c3fh),hl		;0ee1	22 3f 5c	" ? \
	ld hl,(05cc0h)		;0ee4	2a c0 5c	* . \
	add hl,bc		;0ee7	09		.
	ld (05cc0h),hl		;0ee8	22 c0 5c	" . \
	jr l0f3dh		;0eeb	18 50		. P
l0eedh:
	ld a,b			;0eed	78		x
	and a			;0eee	a7		.
	jr z,l0f01h		;0eef	28 10		( .
	and 07fh		;0ef1	e6 7f		. .
	ld b,a			;0ef3	47		G
	in a,(0ffh)		;0ef4	db ff		. .
	and 080h		;0ef6	e6 80		. .
	or b			;0ef8	b0		.
	out (0ffh),a		;0ef9	d3 ff		. .
	ld a,b			;0efb	78		x
	ld (05cc2h),a		;0efc	32 c2 5c	2 . \
	jr l0f3dh		;0eff	18 3c		. <
l0f01h:
	call sub_0e27h		;0f01	cd 27 0e	. ' .
	ld bc,097c0h		;0f04	01 c0 97	. . .
	ld hl,(05c3dh)		;0f07	2a 3d 5c	* = \
	and a			;0f0a	a7		.
	sbc hl,bc		;0f0b	ed 42		. B
	ld (05c3dh),hl		;0f0d	22 3d 5c	" = \
	ld hl,(05c3fh)		;0f10	2a 3f 5c	* ? \
	and a			;0f13	a7		.
	sbc hl,bc		;0f14	ed 42		. B
	ld (05c3fh),hl		;0f16	22 3f 5c	" ? \
	ld hl,(05cc0h)		;0f19	2a c0 5c	* . \
	and a			;0f1c	a7		.
	sbc hl,bc		;0f1d	ed 42		. B
	ld (05cc0h),hl		;0f1f	22 c0 5c	" . \
	ld bc,l12c0h		;0f22	01 c0 12	. . .
	ld hl,06840h		;0f25	21 40 68	! @ h
	ld de,l1750h		;0f28	11 50 17	. P .
	push de			;0f2b	d5		.
	ld de,0ff00h		;0f2c	11 00 ff	. . .
	push de			;0f2f	d5		.
	ld de,l0000h		;0f30	11 00 00	. . .
	push de			;0f33	d5		.
	push de			;0f34	d5		.
	call 065d0h		;0f35	cd d0 65	. . e
	jr l0f3dh		;0f38	18 03		. .
l0f3ah:
	scf			;0f3a	37		7
	jr l0f3eh		;0f3b	18 01		. .
l0f3dh:
	and a			;0f3d	a7		.
l0f3eh:
	pop af			;0f3e	f1		.
	pop hl			;0f3f	e1		.
	pop de			;0f40	d1		.
	pop bc			;0f41	c1		.
	ret			;0f42	c9		.
	ld bc,(05c5dh)		;0f43	ed 4b 5d 5c	. K ] \
	call 0255dh		;0f47	cd 5d 25	. ] %
	ld hl,(05c5dh)		;0f4a	2a 5d 5c	* ] \
	and a			;0f4d	a7		.
	sbc hl,bc		;0f4e	ed 42		. B
	dec hl			;0f50	2b		+
	ld a,l			;0f51	7d		}
	ld hl,(05c65h)		;0f52	2a 65 5c	* e \
	ld (hl),a		;0f55	77		w
	inc hl			;0f56	23		#
	pop bc			;0f57	c1		.
	ld (hl),b		;0f58	70		p
	inc hl			;0f59	23		#
	ld (hl),c		;0f5a	71		q
	inc hl			;0f5b	23		#
	ld (05c65h),hl		;0f5c	22 65 5c	" e \
	ld hl,(05c5dh)		;0f5f	2a 5d 5c	* ] \
	dec hl			;0f62	2b		+
	bit 0,a			;0f63	cb 47		. G
	jr z,l0f73h		;0f65	28 0c		( .
l0f67h:
	dec a			;0f67	3d		=
	ld b,(hl)		;0f68	46		F
	dec hl			;0f69	2b		+
	dec a			;0f6a	3d		=
	jp m,l0f7dh		;0f6b	fa 7d 0f	. } .
	ld c,(hl)		;0f6e	4e		N
	dec hl			;0f6f	2b		+
	push bc			;0f70	c5		.
	jr l0f67h		;0f71	18 f4		. .
l0f73h:
	ld b,020h		;0f73	06 20		.  
	and a			;0f75	a7		.
	ret z			;0f76	c8		.
	ld c,(hl)		;0f77	4e		N
	dec hl			;0f78	2b		+
	dec a			;0f79	3d		=
	push bc			;0f7a	c5		.
	jr l0f67h		;0f7b	18 ea		. .
l0f7dh:
	ld hl,(05c65h)		;0f7d	2a 65 5c	* e \
	dec hl			;0f80	2b		+
	ld a,(hl)		;0f81	7e		~
	dec hl			;0f82	2b		+
	ld (05c65h),hl		;0f83	22 65 5c	" e \
	ld h,(hl)		;0f86	66		f
	ld l,a			;0f87	6f		o
	push hl			;0f88	e5		.
	ret			;0f89	c9		.
sub_0f8ah:
	push af			;0f8a	f5		.
	ld a,(05cc2h)		;0f8b	3a c2 5c	: . \
	and a			;0f8e	a7		.
	jr z,l0f95h		;0f8f	28 04		( .
	pop af			;0f91	f1		.
	jp 0fd32h		;0f92	c3 32 fd	. 2 .
l0f95h:
	pop af			;0f95	f1		.
	jp 06572h		;0f96	c3 72 65	. r e
sub_0f99h:
	push af			;0f99	f5		.
	ld a,(05cc2h)		;0f9a	3a c2 5c	: . \
	and a			;0f9d	a7		.
	jr z,l0fa4h		;0f9e	28 04		( .
	pop af			;0fa0	f1		.
	jp 0fd90h		;0fa1	c3 90 fd	. . .
l0fa4h:
	pop af			;0fa4	f1		.
	jp 065d0h		;0fa5	c3 d0 65	. . e
	nop			;0fa8	00		.
	nop			;0fa9	00		.
	nop			;0faa	00		.
	nop			;0fab	00		.
	nop			;0fac	00		.
	nop			;0fad	00		.
	nop			;0fae	00		.
	nop			;0faf	00		.
	nop			;0fb0	00		.
	nop			;0fb1	00		.
	nop			;0fb2	00		.
	nop			;0fb3	00		.
	nop			;0fb4	00		.
	nop			;0fb5	00		.
	nop			;0fb6	00		.
	nop			;0fb7	00		.
	nop			;0fb8	00		.
	nop			;0fb9	00		.
	nop			;0fba	00		.
	nop			;0fbb	00		.
	nop			;0fbc	00		.
	nop			;0fbd	00		.
	nop			;0fbe	00		.
	nop			;0fbf	00		.
	nop			;0fc0	00		.
	nop			;0fc1	00		.
	nop			;0fc2	00		.
	nop			;0fc3	00		.
	nop			;0fc4	00		.
	nop			;0fc5	00		.
	nop			;0fc6	00		.
	nop			;0fc7	00		.
	nop			;0fc8	00		.
	nop			;0fc9	00		.
	nop			;0fca	00		.
	nop			;0fcb	00		.
	nop			;0fcc	00		.
	nop			;0fcd	00		.
	nop			;0fce	00		.
	nop			;0fcf	00		.
	nop			;0fd0	00		.
	nop			;0fd1	00		.
	nop			;0fd2	00		.
	nop			;0fd3	00		.
	nop			;0fd4	00		.
	nop			;0fd5	00		.
	nop			;0fd6	00		.
	nop			;0fd7	00		.
	nop			;0fd8	00		.
	nop			;0fd9	00		.
	nop			;0fda	00		.
	nop			;0fdb	00		.
	nop			;0fdc	00		.
	nop			;0fdd	00		.
	nop			;0fde	00		.
	nop			;0fdf	00		.
	nop			;0fe0	00		.
	nop			;0fe1	00		.
	nop			;0fe2	00		.
	nop			;0fe3	00		.
	nop			;0fe4	00		.
	nop			;0fe5	00		.
	nop			;0fe6	00		.
	nop			;0fe7	00		.
	nop			;0fe8	00		.
	nop			;0fe9	00		.
	nop			;0fea	00		.
	nop			;0feb	00		.
	nop			;0fec	00		.
	nop			;0fed	00		.
	nop			;0fee	00		.
	nop			;0fef	00		.
	nop			;0ff0	00		.
	nop			;0ff1	00		.
	nop			;0ff2	00		.
	nop			;0ff3	00		.
	nop			;0ff4	00		.
	nop			;0ff5	00		.
	nop			;0ff6	00		.
	nop			;0ff7	00		.
	nop			;0ff8	00		.
	nop			;0ff9	00		.
	nop			;0ffa	00		.
	nop			;0ffb	00		.
	nop			;0ffc	00		.
	nop			;0ffd	00		.
	nop			;0ffe	00		.
	nop			;0fff	00		.
	ld ix,l0000h		;1000	dd 21 00 00	. ! . .
	add ix,sp		;1004	dd 39		. 9
	push bc			;1006	c5		.
	push af			;1007	f5		.
	push bc			;1008	c5		.
	push de			;1009	d5		.
	push hl			;100a	e5		.
	ld e,(ix+002h)		;100b	dd 5e 02	. ^ .
	ld d,(ix+003h)		;100e	dd 56 03	. V .
	xor a			;1011	af		.
	sla e			;1012	cb 23		. #
	rl d			;1014	cb 12		. .
	rla			;1016	17		.
	ld hl,l000bh+2		;1017	21 0d 00	! . .
	sla l			;101a	cb 25		. %
	rl h			;101c	cb 14		. .
	and a			;101e	a7		.
	sbc hl,de		;101f	ed 52		. R
	jr nc,l1038h		;1021	30 15		0 .
	ld hl,l0017h+1		;1023	21 18 00	! . .
	sla l			;1026	cb 25		. %
	rl h			;1028	cb 14		. .
	and a			;102a	a7		.
	sbc hl,de		;102b	ed 52		. R
	jr c,l103eh		;102d	38 0f		8 .
	ld b,0ffh		;102f	06 ff		. .
	call 06405h		;1031	cd 05 64	. . d
	ld b,0ffh		;1034	06 ff		. .
	jr l1042h		;1036	18 0a		. .
l1038h:
	ld b,0feh		;1038	06 fe		. .
	ld c,0feh		;103a	0e fe		. .
	jr l1042h		;103c	18 04		. .
l103eh:
	ld b,0ffh		;103e	06 ff		. .
	ld c,000h		;1040	0e 00		. .
l1042h:
	push af			;1042	f5		.
	push bc			;1043	c5		.
	ld hl,l1fffh		;1044	21 ff 1f	! . .
	scf			;1047	37		7
	sbc hl,de		;1048	ed 52		. R
	ld b,0feh		;104a	06 fe		. .
	call 06316h		;104c	cd 16 63	. . c
	ex de,hl		;104f	eb		.
	pop bc			;1050	c1		.
	pop af			;1051	f1		.
	and a			;1052	a7		.
	jr z,l1074h		;1053	28 1f		( .
	ld (ix-002h),c		;1055	dd 71 fe	. q .
	ld (ix-001h),b		;1058	dd 70 ff	. p .
	ld l,(ix+000h)		;105b	dd 6e 00	. n .
	ld h,(ix+001h)		;105e	dd 66 01	. f .
	ld (ix+003h),h		;1061	dd 74 03	. t .
	ld (ix+002h),l		;1064	dd 75 02	. u .
	ld (ix+001h),d		;1067	dd 72 01	. r .
	ld (ix+000h),e		;106a	dd 73 00	. s .
	pop hl			;106d	e1		.
	pop de			;106e	d1		.
	pop bc			;106f	c1		.
	pop af			;1070	f1		.
	call 06572h		;1071	cd 72 65	. r e
l1074h:
	ld l,(ix+000h)		;1074	dd 6e 00	. n .
	ld h,(ix+001h)		;1077	dd 66 01	. f .
	push hl			;107a	e5		.
	ld l,(ix+004h)		;107b	dd 6e 04	. n .
	ld h,(ix+005h)		;107e	dd 66 05	. f .
	ld (ix-002h),l		;1081	dd 75 fe	. u .
	ld (ix-001h),h		;1084	dd 74 ff	. t .
	ld l,(ix+006h)		;1087	dd 6e 06	. n .
	ld h,(ix+007h)		;108a	dd 66 07	. f .
	ld (ix+000h),l		;108d	dd 75 00	. u .
	ld (ix+001h),h		;1090	dd 74 01	. t .
	ld (ix+002h),c		;1093	dd 71 02	. q .
	ld (ix+003h),b		;1096	dd 70 03	. p .
	ld (ix+004h),e		;1099	dd 73 04	. s .
	ld (ix+005h),d		;109c	dd 72 05	. r .
	pop hl			;109f	e1		.
	ld (ix+006h),l		;10a0	dd 75 06	. u .
	ld (ix+007h),h		;10a3	dd 74 07	. t .
	pop hl			;10a6	e1		.
	pop de			;10a7	d1		.
	pop bc			;10a8	c1		.
	pop af			;10a9	f1		.
	call 065d0h		;10aa	cd d0 65	. . e
	ret			;10ad	c9		.
	push af			;10ae	f5		.
	push hl			;10af	e5		.
	push ix			;10b0	dd e5		. .
	ld hl,l0000h		;10b2	21 00 00	! . .
	add hl,sp		;10b5	39		9
	push de			;10b6	d5		.
	ld a,(06315h)		;10b7	3a 15 63	: . c
	ld e,a			;10ba	5f		_
	ld d,000h		;10bb	16 00		. .
	inc de			;10bd	13		.
	inc de			;10be	13		.
	and a			;10bf	a7		.
	sbc hl,de		;10c0	ed 52		. R
	ex de,hl		;10c2	eb		.
	ld ix,l0000h		;10c3	dd 21 00 00	. ! . .
	add ix,de		;10c7	dd 19		. .
	pop de			;10c9	d1		.
	ld sp,ix		;10ca	dd f9		. .
	call 0651eh		;10cc	cd 1e 65	. . e
	push bc			;10cf	c5		.
	ld b,0ffh		;10d0	06 ff		. .
	call 06405h		;10d2	cd 05 64	. . d
	ld b,0ffh		;10d5	06 ff		. .
	ld a,c			;10d7	79		y
	and 0f8h		;10d8	e6 f8		. .
	ld c,a			;10da	4f		O
	call 06499h		;10db	cd 99 64	. . d
	pop bc			;10de	c1		.
	ld hl,(05c78h)		;10df	2a 78 5c	* x \
	inc hl			;10e2	23		#
	ld (05c78h),hl		;10e3	22 78 5c	" x \
	ld a,h			;10e6	7c		|
	or l			;10e7	b5		.
	jr nz,l10edh		;10e8	20 03		  .
	inc (iy+040h)		;10ea	fd 34 40	. 4 @
l10edh:
	push bc			;10ed	c5		.
	push de			;10ee	d5		.
	call sub_02e1h		;10ef	cd e1 02	. . .
	pop de			;10f2	d1		.
	pop bc			;10f3	c1		.
	ld ix,l0000h		;10f4	dd 21 00 00	. ! . .
	add ix,sp		;10f8	dd 39		. 9
	call 0654ah		;10fa	cd 4a 65	. J e
	inc ix			;10fd	dd 23		. #
	ld sp,ix		;10ff	dd f9		. .
	pop ix			;1101	dd e1		. .
	pop hl			;1103	e1		.
	pop af			;1104	f1		.
	ei			;1105	fb		.
	ret			;1106	c9		.
	push af			;1107	f5		.
	push hl			;1108	e5		.
	ld hl,(05cb0h)		;1109	2a b0 5c	* . \
	ld a,h			;110c	7c		|
	or l			;110d	b5		.
	jr nz,l1111h		;110e	20 01		  .
	jp (hl)			;1110	e9		.
l1111h:
	pop hl			;1111	e1		.
	pop af			;1112	f1		.
	retn			;1113	ed 45		. E
	rst 38h			;1115	ff		.
	push af			;1116	f5		.
	push bc			;1117	c5		.
	push de			;1118	d5		.
	call 0645eh		;1119	cd 5e 64	. ^ d
	push af			;111c	f5		.
	ld d,b			;111d	50		P
	ld b,a			;111e	47		G
	call 06405h		;111f	cd 05 64	. . d
	push bc			;1122	c5		.
	call 0644dh		;1123	cd 4d 64	. M d
	cpl			;1126	2f		/
	ld b,d			;1127	42		B
	ld c,a			;1128	4f		O
	call 06499h		;1129	cd 99 64	. . d
	ld e,(hl)		;112c	5e		^
	inc hl			;112d	23		#
	ld d,(hl)		;112e	56		V
	dec hl			;112f	2b		+
	ex de,hl		;1130	eb		.
	pop bc			;1131	c1		.
	pop af			;1132	f1		.
	ld b,a			;1133	47		G
	call 06499h		;1134	cd 99 64	. . d
	pop de			;1137	d1		.
	pop bc			;1138	c1		.
	pop af			;1139	f1		.
	ret			;113a	c9		.
	push af			;113b	f5		.
	push bc			;113c	c5		.
	call 0645eh		;113d	cd 5e 64	. ^ d
	push af			;1140	f5		.
	ld d,b			;1141	50		P
	ld b,a			;1142	47		G
	call 06405h		;1143	cd 05 64	. . d
	push bc			;1146	c5		.
	call 0644dh		;1147	cd 4d 64	. M d
	cpl			;114a	2f		/
	ld b,d			;114b	42		B
	ld c,a			;114c	4f		O
	call 06499h		;114d	cd 99 64	. . d
	ld (hl),e		;1150	73		s
	inc hl			;1151	23		#
	ld (hl),d		;1152	72		r
	dec hl			;1153	2b		+
	pop bc			;1154	c1		.
	pop af			;1155	f1		.
	call 06499h		;1156	cd 99 64	. . d
	pop bc			;1159	c1		.
	pop af			;115a	f1		.
	ret			;115b	c9		.
	push af			;115c	f5		.
	push bc			;115d	c5		.
	push hl			;115e	e5		.
	ld h,d			;115f	62		b
	ld l,000h		;1160	2e 00		. .
	ld a,(0c000h)		;1162	3a 00 c0	: . .
	push af			;1165	f5		.
	ld a,(hl)		;1166	7e		~
	push af			;1167	f5		.
	ld a,007h		;1168	3e 07		> .
	out (0f5h),a		;116a	d3 f5		. .
	in a,(0f6h)		;116c	db f6		. .
	ld b,a			;116e	47		G
	ld a,00eh		;116f	3e 0e		> .
	out (0f5h),a		;1171	d3 f5		. .
	in a,(0f6h)		;1173	db f6		. .
	ld c,a			;1175	4f		O
	ld a,007h		;1176	3e 07		> .
	out (0f5h),a		;1178	d3 f5		. .
	ld a,040h		;117a	3e 40		> @
	out (0f6h),a		;117c	d3 f6		. .
	ld a,00eh		;117e	3e 0e		> .
	out (0f5h),a		;1180	d3 f5		. .
	xor a			;1182	af		.
	out (0f6h),a		;1183	d3 f6		. .
	ld a,002h		;1185	3e 02		> .
	ld (0c000h),a		;1187	32 00 c0	2 . .
	ld a,e			;118a	7b		{
	ld (hl),a		;118b	77		w
	sra a			;118c	cb 2f		. /
	sra a			;118e	cb 2f		. /
	sra a			;1190	cb 2f		. /
	sra a			;1192	cb 2f		. /
	ld (hl),a		;1194	77		w
	ld a,007h		;1195	3e 07		> .
	out (0f5h),a		;1197	d3 f5		. .
	ld a,b			;1199	78		x
	out (0f6h),a		;119a	d3 f6		. .
	ld a,00eh		;119c	3e 0e		> .
	out (0f5h),a		;119e	d3 f5		. .
	ld a,c			;11a0	79		y
	out (0f6h),a		;11a1	d3 f6		. .
	pop af			;11a3	f1		.
	ld (hl),a		;11a4	77		w
	pop af			;11a5	f1		.
	ld (0c000h),a		;11a6	32 00 c0	2 . .
	pop hl			;11a9	e1		.
	pop bc			;11aa	c1		.
	pop af			;11ab	f1		.
	ret			;11ac	c9		.
	push af			;11ad	f5		.
	push bc			;11ae	c5		.
	push hl			;11af	e5		.
	ld h,d			;11b0	62		b
	ld l,000h		;11b1	2e 00		. .
	ld a,(0c000h)		;11b3	3a 00 c0	: . .
	push af			;11b6	f5		.
	ld a,(hl)		;11b7	7e		~
	push af			;11b8	f5		.
	ld a,007h		;11b9	3e 07		> .
	out (0f5h),a		;11bb	d3 f5		. .
	in a,(0f6h)		;11bd	db f6		. .
	ld b,a			;11bf	47		G
	ld a,00eh		;11c0	3e 0e		> .
	out (0f5h),a		;11c2	d3 f5		. .
	in a,(0f6h)		;11c4	db f6		. .
	ld c,a			;11c6	4f		O
	push bc			;11c7	c5		.
	ld a,007h		;11c8	3e 07		> .
	out (0f5h),a		;11ca	d3 f5		. .
	ld a,040h		;11cc	3e 40		> @
	out (0f6h),a		;11ce	d3 f6		. .
	ld a,00eh		;11d0	3e 0e		> .
	out (0f5h),a		;11d2	d3 f5		. .
	xor a			;11d4	af		.
	out (0f6h),a		;11d5	d3 f6		. .
	ld a,002h		;11d7	3e 02		> .
	ld (0c000h),a		;11d9	32 00 c0	2 . .
	ld a,(hl)		;11dc	7e		~
	and 00fh		;11dd	e6 0f		. .
	ld c,a			;11df	4f		O
	ld h,e			;11e0	63		c
	ld a,(hl)		;11e1	7e		~
	sla a			;11e2	cb 27		. '
	sla a			;11e4	cb 27		. '
	sla a			;11e6	cb 27		. '
	sla a			;11e8	cb 27		. '
	or c			;11ea	b1		.
	ld e,a			;11eb	5f		_
	pop bc			;11ec	c1		.
	ld a,007h		;11ed	3e 07		> .
	out (0f5h),a		;11ef	d3 f5		. .
	ld a,b			;11f1	78		x
	out (0f6h),a		;11f2	d3 f6		. .
	ld a,00eh		;11f4	3e 0e		> .
	out (0f5h),a		;11f6	d3 f5		. .
	ld a,c			;11f8	79		y
	out (0f6h),a		;11f9	d3 f6		. .
	pop af			;11fb	f1		.
	ld (hl),a		;11fc	77		w
	pop af			;11fd	f1		.
	ld (0c000h),a		;11fe	32 00 c0	2 . .
	pop hl			;1201	e1		.
	pop bc			;1202	c1		.
	pop af			;1203	f1		.
	ret			;1204	c9		.
	push af			;1205	f5		.
	push de			;1206	d5		.
	ld a,b			;1207	78		x
	cp 0feh			;1208	fe fe		. .
	jr z,l123ah		;120a	28 2e		( .
	cp 0ffh			;120c	fe ff		. .
	jr z,l122dh		;120e	28 1d		( .
	and a			;1210	a7		.
	jr z,l1232h		;1211	28 1f		( .
	ld d,080h		;1213	16 80		. .
	ld e,b			;1215	58		X
	call 0635ch		;1216	cd 5c 63	. \ c
	ld d,040h		;1219	16 40		. @
	ld e,080h		;121b	1e 80		. .
	call 063adh		;121d	cd ad 63	. . c
	ld a,e			;1220	7b		{
	cpl			;1221	2f		/
	ld c,a			;1222	4f		O
	ld d,0a0h		;1223	16 a0		. .
	ld e,0c0h		;1225	1e c0		. .
	call 063adh		;1227	cd ad 63	. . c
	ld b,e			;122a	43		C
	jr l124ah		;122b	18 1d		. .
l122dh:
	ld bc,l0000h		;122d	01 00 00	. . .
l1230h:
	jr l124ah		;1230	18 18		. .
l1232h:
	in a,(0f4h)		;1232	db f4		. .
	cpl			;1234	2f		/
	ld b,a			;1235	47		G
	ld c,000h		;1236	0e 00		. .
	jr l124ah		;1238	18 10		. .
l123ah:
	in a,(0ffh)		;123a	db ff		. .
	and 080h		;123c	e6 80		. .
	cpl			;123e	2f		/
	rlca			;123f	07		.
	ld b,a			;1240	47		G
	in a,(0f4h)		;1241	db f4		. .
	cpl			;1243	2f		/
	and 001h		;1244	e6 01		. .
	or b			;1246	b0		.
	ld b,a			;1247	47		G
	ld c,000h		;1248	0e 00		. .
l124ah:
	pop de			;124a	d1		.
	pop af			;124b	f1		.
	ret			;124c	c9		.
	push bc			;124d	c5		.
	ld a,h			;124e	7c		|
	ld b,005h		;124f	06 05		. .
l1251h:
	srl a			;1251	cb 3f		. ?
	djnz l1251h		;1253	10 fc		. .
	inc a			;1255	3c		<
	ld b,a			;1256	47		G
	xor a			;1257	af		.
	scf			;1258	37		7
l1259h:
	rla			;1259	17		.
	djnz l1259h		;125a	10 fd		. .
	pop bc			;125c	c1		.
	ret			;125d	c9		.
	push bc			;125e	c5		.
	push de			;125f	d5		.
	call 0644dh		;1260	cd 4d 64	. M d
	ld c,a			;1263	4f		O
	ld a,(06315h)		;1264	3a 15 63	: . c
	and a			;1267	a7		.
	jr z,l1274h		;1268	28 0a		( .
	ld b,a			;126a	47		G
l126bh:
	ld e,b			;126b	58		X
	call 06405h		;126c	cd 05 64	. . d
	and c			;126f	a1		.
	jr z,l1295h		;1270	28 23		( #
	djnz l126bh		;1272	10 f7		. .
l1274h:
	in a,(0f4h)		;1274	db f4		. .
	cpl			;1276	2f		/
	and c			;1277	a1		.
	jr z,l1292h		;1278	28 18		( .
	dec c			;127a	0d		.
	jr nz,l128eh		;127b	20 11		  .
	in a,(0ffh)		;127d	db ff		. .
	and 080h		;127f	e6 80		. .
	ld d,a			;1281	57		W
	in a,(0f4h)		;1282	db f4		. .
	and 001h		;1284	e6 01		. .
	rrca			;1286	0f		.
	and d			;1287	a2		.
	jr z,l128eh		;1288	28 04		( .
	ld a,0feh		;128a	3e fe		> .
	jr l1296h		;128c	18 08		. .
l128eh:
	ld a,0ffh		;128e	3e ff		> .
	jr l1296h		;1290	18 04		. .
l1292h:
	xor a			;1292	af		.
	jr l1296h		;1293	18 01		. .
l1295h:
	ld a,b			;1295	78		x
l1296h:
	pop de			;1296	d1		.
	pop bc			;1297	c1		.
	ret			;1298	c9		.
	push af			;1299	f5		.
	push bc			;129a	c5		.
	push de			;129b	d5		.
	push hl			;129c	e5		.
	ld h,b			;129d	60		`
	ld a,(06315h)		;129e	3a 15 63	: . c
	and a			;12a1	a7		.
	jr z,l12b5h		;12a2	28 11		( .
	ld d,080h		;12a4	16 80		. .
	ld e,000h		;12a6	1e 00		. .
	call 0635ch		;12a8	cd 5c 63	. \ c
	ld d,0a0h		;12ab	16 a0		. .
	push af			;12ad	f5		.
	ld a,c			;12ae	79		y
	cpl			;12af	2f		/
	ld e,a			;12b0	5f		_
	pop af			;12b1	f1		.
	call 0635ch		;12b2	cd 5c 63	. \ c
l12b5h:
	ld a,b			;12b5	78		x
	and a			;12b6	a7		.
	jr nz,l12cah		;12b7	20 11		  .
	ld a,c			;12b9	79		y
	cp 0ffh			;12ba	fe ff		. .
	jr z,l12c4h		;12bc	28 06		( .
	in a,(0ffh)		;12be	db ff		. .
l12c0h:
	res 7,a			;12c0	cb bf		. .
	out (0ffh),a		;12c2	d3 ff		. .
l12c4h:
	ld a,c			;12c4	79		y
	cpl			;12c5	2f		/
	out (0f4h),a		;12c6	d3 f4		. .
	jr l1319h		;12c8	18 4f		. O
l12cah:
	ld a,b			;12ca	78		x
	cp 0feh			;12cb	fe fe		. .
	jr nz,l12ech		;12cd	20 1d		  .
	in a,(0ffh)		;12cf	db ff		. .
	rla			;12d1	17		.
	rr c			;12d2	cb 19		. .
	ccf			;12d4	3f		?
	rra			;12d5	1f		.
	out (0ffh),a		;12d6	d3 ff		. .
	bit 7,a			;12d8	cb 7f		. .
	jr nz,l12e4h		;12da	20 08		  .
	in a,(0f4h)		;12dc	db f4		. .
	res 0,a			;12de	cb 87		. .
	out (0f4h),a		;12e0	d3 f4		. .
	jr l1319h		;12e2	18 35		. 5
l12e4h:
	in a,(0f4h)		;12e4	db f4		. .
	set 0,a			;12e6	cb c7		. .
	out (0f4h),a		;12e8	d3 f4		. .
	jr l1319h		;12ea	18 2d		. -
l12ech:
	in a,(0f4h)		;12ec	db f4		. .
	cpl			;12ee	2f		/
	ld e,a			;12ef	5f		_
	ld a,c			;12f0	79		y
	cpl			;12f1	2f		/
	or e			;12f2	b3		.
	cpl			;12f3	2f		/
	out (0f4h),a		;12f4	d3 f4		. .
	bit 0,c			;12f6	cb 41		. A
	jr nz,l1306h		;12f8	20 0c		  .
	in a,(0ffh)		;12fa	db ff		. .
	res 7,a			;12fc	cb bf		. .
	out (0ffh),a		;12fe	d3 ff		. .
	in a,(0f4h)		;1300	db f4		. .
	res 0,a			;1302	cb 87		. .
	out (0f4h),a		;1304	d3 f4		. .
l1306h:
	ld a,b			;1306	78		x
	cp 0ffh			;1307	fe ff		. .
	jr z,l1319h		;1309	28 0e		( .
	ld d,080h		;130b	16 80		. .
	ld e,b			;130d	58		X
	call 0635ch		;130e	cd 5c 63	. \ c
	ld d,040h		;1311	16 40		. @
	ld a,c			;1313	79		y
	cpl			;1314	2f		/
	ld e,a			;1315	5f		_
	call 0635ch		;1316	cd 5c 63	. \ c
l1319h:
	pop hl			;1319	e1		.
	pop de			;131a	d1		.
	pop bc			;131b	c1		.
	pop af			;131c	f1		.
	ret			;131d	c9		.
	push af			;131e	f5		.
	push bc			;131f	c5		.
	push de			;1320	d5		.
	in a,(0ffh)		;1321	db ff		. .
	nop			;1323	00		.
	nop			;1324	00		.
	ld (ix+000h),a		;1325	dd 77 00	. w .
	inc ix			;1328	dd 23		. #
	in a,(0f4h)		;132a	db f4		. .
	ld (ix+000h),a		;132c	dd 77 00	. w .
	inc ix			;132f	dd 23		. #
	ld a,(06315h)		;1331	3a 15 63	: . c
	and a			;1334	a7		.
	jr z,l1344h		;1335	28 0d		( .
	ld b,a			;1337	47		G
l1338h:
	ld e,b			;1338	58		X
	call 06405h		;1339	cd 05 64	. . d
	ld (ix+000h),c		;133c	dd 71 00	. q .
	inc ix			;133f	dd 23		. #
	ld b,e			;1341	43		C
	djnz l1338h		;1342	10 f4		. .
l1344h:
	dec ix			;1344	dd 2b		. +
	pop de			;1346	d1		.
	pop bc			;1347	c1		.
	pop af			;1348	f1		.
	ret			;1349	c9		.
	push af			;134a	f5		.
	push bc			;134b	c5		.
	push de			;134c	d5		.
	ld a,(ix+000h)		;134d	dd 7e 00	. ~ .
	out (0ffh),a		;1350	d3 ff		. .
	inc ix			;1352	dd 23		. #
l1354h:
	ld a,(ix+000h)		;1354	dd 7e 00	. ~ .
	out (0f4h),a		;1357	d3 f4		. .
	inc ix			;1359	dd 23		. #
	ld a,(06315h)		;135b	3a 15 63	: . c
	and a			;135e	a7		.
	jr z,l136ch		;135f	28 0b		( .
	ld b,a			;1361	47		G
l1362h:
	ld c,(ix+000h)		;1362	dd 4e 00	. N .
	call 06499h		;1365	cd 99 64	. . d
	inc ix			;1368	dd 23		. #
	djnz l1362h		;136a	10 f6		. .
l136ch:
	dec ix			;136c	dd 2b		. +
	pop de			;136e	d1		.
	pop bc			;136f	c1		.
	pop af			;1370	f1		.
	ret			;1371	c9		.
	ld ix,l0000h		;1372	dd 21 00 00	. ! . .
	add ix,sp		;1376	dd 39		. 9
	ld (ix+000h),c		;1378	dd 71 00	. q .
	ld (ix+001h),b		;137b	dd 70 01	. p .
	ld c,(ix+002h)		;137e	dd 4e 02	. N .
	ld b,(ix+003h)		;1381	dd 46 03	. F .
	call 06499h		;1384	cd 99 64	. . d
	pop bc			;1387	c1		.
	pop ix			;1388	dd e1		. .
	pop ix			;138a	dd e1		. .
	jp (ix)			;138c	dd e9		. .
	rst 38h			;138e	ff		.
	rst 38h			;138f	ff		.
	rst 38h			;1390	ff		.
	rst 38h			;1391	ff		.
	rst 38h			;1392	ff		.
	rst 38h			;1393	ff		.
	rst 38h			;1394	ff		.
	rst 38h			;1395	ff		.
	rst 38h			;1396	ff		.
	rst 38h			;1397	ff		.
	rst 38h			;1398	ff		.
	rst 38h			;1399	ff		.
	rst 38h			;139a	ff		.
	rst 38h			;139b	ff		.
	rst 38h			;139c	ff		.
	rst 38h			;139d	ff		.
	rst 38h			;139e	ff		.
	rst 38h			;139f	ff		.
	rst 38h			;13a0	ff		.
	rst 38h			;13a1	ff		.
	rst 38h			;13a2	ff		.
	rst 38h			;13a3	ff		.
	rst 38h			;13a4	ff		.
	rst 38h			;13a5	ff		.
	rst 38h			;13a6	ff		.
	rst 38h			;13a7	ff		.
	rst 38h			;13a8	ff		.
	rst 38h			;13a9	ff		.
	rst 38h			;13aa	ff		.
	rst 38h			;13ab	ff		.
	rst 38h			;13ac	ff		.
	rst 38h			;13ad	ff		.
	rst 38h			;13ae	ff		.
	rst 38h			;13af	ff		.
	rst 38h			;13b0	ff		.
	rst 38h			;13b1	ff		.
	rst 38h			;13b2	ff		.
	rst 38h			;13b3	ff		.
	rst 38h			;13b4	ff		.
	rst 38h			;13b5	ff		.
	rst 38h			;13b6	ff		.
	rst 38h			;13b7	ff		.
	rst 38h			;13b8	ff		.
	rst 38h			;13b9	ff		.
	rst 38h			;13ba	ff		.
	rst 38h			;13bb	ff		.
	rst 38h			;13bc	ff		.
	rst 38h			;13bd	ff		.
	rst 38h			;13be	ff		.
	rst 38h			;13bf	ff		.
	rst 38h			;13c0	ff		.
	rst 38h			;13c1	ff		.
	rst 38h			;13c2	ff		.
	rst 38h			;13c3	ff		.
	rst 38h			;13c4	ff		.
	rst 38h			;13c5	ff		.
	rst 38h			;13c6	ff		.
	rst 38h			;13c7	ff		.
	rst 38h			;13c8	ff		.
	rst 38h			;13c9	ff		.
	rst 38h			;13ca	ff		.
	rst 38h			;13cb	ff		.
	rst 38h			;13cc	ff		.
	rst 38h			;13cd	ff		.
	rst 38h			;13ce	ff		.
	rst 38h			;13cf	ff		.
	ex (sp),hl		;13d0	e3		.
	ld ix,(065ceh)		;13d1	dd 2a ce 65	. * . e
	dec ix			;13d5	dd 2b		. +
	ld (ix+000h),h		;13d7	dd 74 00	. t .
	dec ix			;13da	dd 2b		. +
	ld (ix+000h),l		;13dc	dd 75 00	. u .
	pop hl			;13df	e1		.
	ex (sp),hl		;13e0	e3		.
	dec ix			;13e1	dd 2b		. +
	ld (ix+000h),h		;13e3	dd 74 00	. t .
	dec ix			;13e6	dd 2b		. +
	ld (ix+000h),l		;13e8	dd 75 00	. u .
	ld (065ceh),ix		;13eb	dd 22 ce 65	. " . e
	push de			;13ef	d5		.
	push bc			;13f0	c5		.
	push af			;13f1	f5		.
	ld hl,l0000h		;13f2	21 00 00	! . .
	add hl,sp		;13f5	39		9
	ld d,h			;13f6	54		T
	ld e,l			;13f7	5d		]
	ld a,(06315h)		;13f8	3a 15 63	: . c
	ld c,a			;13fb	4f		O
	ld b,000h		;13fc	06 00		. .
	inc bc			;13fe	03		.
	inc bc			;13ff	03		.
	and a			;1400	a7		.
	sbc hl,bc		;1401	ed 42		. B
	ld sp,hl		;1403	f9		.
	ld ix,l0000h		;1404	dd 21 00 00	. ! . .
	add ix,de		;1408	dd 19		. .
	ex de,hl		;140a	eb		.
	ld c,(ix+008h)		;140b	dd 4e 08	. N .
	ld b,(ix+008h)		;140e	dd 46 08	. F .
	ld a,00eh		;1411	3e 0e		> .
	add a,c			;1413	81		.
	ld c,a			;1414	4f		O
	jr nc,l1418h		;1415	30 01		0 .
	inc b			;1417	04		.
l1418h:
	ldir			;1418	ed b0		. .
	push de			;141a	d5		.
	pop ix			;141b	dd e1		. .
	call 0651eh		;141d	cd 1e 65	. . e
	ld ix,l0000h		;1420	dd 21 00 00	. ! . .
	add ix,sp		;1424	dd 39		. 9
	ld c,(ix+00ah)		;1426	dd 4e 0a	. N .
	ld b,(ix+00bh)		;1429	dd 46 0b	. F .
	call 06499h		;142c	cd 99 64	. . d
	pop af			;142f	f1		.
	pop bc			;1430	c1		.
	pop de			;1431	d1		.
	pop hl			;1432	e1		.
	pop ix			;1433	dd e1		. .
	pop ix			;1435	dd e1		. .
	pop ix			;1437	dd e1		. .
	call 0658ch		;1439	cd 8c 65	. . e
	push af			;143c	f5		.
	push bc			;143d	c5		.
	push de			;143e	d5		.
	push hl			;143f	e5		.
	ld ix,(065ceh)		;1440	dd 2a ce 65	. * . e
	ld c,(ix+000h)		;1444	dd 4e 00	. N .
	inc ix			;1447	dd 23		. #
	ld b,(ix+000h)		;1449	dd 46 00	. F .
	inc ix			;144c	dd 23		. #
	ld (065ceh),ix		;144e	dd 22 ce 65	. " . e
	ld ix,l0000h		;1452	dd 21 00 00	. ! . .
	add ix,sp		;1456	dd 39		. 9
	ld a,008h		;1458	3e 08		> .
	add a,c			;145a	81		.
	ld c,a			;145b	4f		O
	jr nc,l145fh		;145c	30 01		0 .
	inc b			;145e	04		.
l145fh:
	add ix,bc		;145f	dd 09		. .
	push ix			;1461	dd e5		. .
	pop hl			;1463	e1		.
	dec hl			;1464	2b		+
	call 0654ah		;1465	cd 4a 65	. J e
	push ix			;1468	dd e5		. .
	pop de			;146a	d1		.
	lddr			;146b	ed b8		. .
	ex de,hl		;146d	eb		.
	inc hl			;146e	23		#
	ld sp,hl		;146f	f9		.
	ld ix,(065ceh)		;1470	dd 2a ce 65	. * . e
	ld c,(ix+000h)		;1474	dd 4e 00	. N .
	inc ix			;1477	dd 23		. #
	ld b,(ix+000h)		;1479	dd 46 00	. F .
	inc ix			;147c	dd 23		. #
	ld (065ceh),ix		;147e	dd 22 ce 65	. " . e
	push bc			;1482	c5		.
	pop ix			;1483	dd e1		. .
	pop hl			;1485	e1		.
	pop de			;1486	d1		.
	pop bc			;1487	c1		.
	pop af			;1488	f1		.
	push ix			;1489	dd e5		. .
	ret			;148b	c9		.
	push hl			;148c	e5		.
	push de			;148d	d5		.
	push bc			;148e	c5		.
	ld c,b			;148f	48		H
	ld b,(ix+009h)		;1490	dd 46 09	. F .
	call 06499h		;1493	cd 99 64	. . d
	ld b,d			;1496	42		B
	ld c,e			;1497	4b		K
	ld e,(ix+000h)		;1498	dd 5e 00	. ^ .
	ld d,(ix+001h)		;149b	dd 56 01	. V .
	ld l,(ix+006h)		;149e	dd 6e 06	. n .
	ld h,(ix+007h)		;14a1	dd 66 07	. f .
	rlca			;14a4	07		.
	rrca			;14a5	0f		.
	jr c,l14adh		;14a6	38 05		8 .
	ldir			;14a8	ed b0		. .
	add hl,bc		;14aa	09		.
	jr l14b2h		;14ab	18 05		. .
l14adh:
	lddr			;14ad	ed b8		. .
	and a			;14af	a7		.
	sbc hl,bc		;14b0	ed 42		. B
l14b2h:
	ld (ix+006h),l		;14b2	dd 75 06	. u .
	ld (ix+007h),h		;14b5	dd 74 07	. t .
	pop bc			;14b8	c1		.
	pop hl			;14b9	e1		.
	push hl			;14ba	e5		.
	push bc			;14bb	c5		.
	ld b,(ix+008h)		;14bc	dd 46 08	. F .
	call 06499h		;14bf	cd 99 64	. . d
	ld b,h			;14c2	44		D
	ld c,l			;14c3	4d		M
	ld e,(ix+004h)		;14c4	dd 5e 04	. ^ .
	ld d,(ix+005h)		;14c7	dd 56 05	. V .
	ld l,(ix+000h)		;14ca	dd 6e 00	. n .
	ld h,(ix+001h)		;14cd	dd 66 01	. f .
	rlca			;14d0	07		.
	rrca			;14d1	0f		.
	jr c,l14d9h		;14d2	38 05		8 .
	ldir			;14d4	ed b0		. .
	add hl,bc		;14d6	09		.
	jr l14deh		;14d7	18 05		. .
l14d9h:
	lddr			;14d9	ed b8		. .
	and a			;14db	a7		.
	sbc hl,bc		;14dc	ed 42		. B
l14deh:
	ld (ix+004h),l		;14de	dd 75 04	. u .
	ld (ix+005h),h		;14e1	dd 74 05	. t .
	pop bc			;14e4	c1		.
	pop de			;14e5	d1		.
	pop hl			;14e6	e1		.
	ret			;14e7	c9		.
	ld d,h			;14e8	54		T
	ld e,l			;14e9	5d		]
	ld c,(ix+002h)		;14ea	dd 4e 02	. N .
	ld b,(ix+003h)		;14ed	dd 46 03	. F .
	ld a,(ix+000h)		;14f0	dd 7e 00	. ~ .
	rlca			;14f3	07		.
	rrca			;14f4	0f		.
	jr c,l14fah		;14f5	38 03		8 .
	add hl,bc		;14f7	09		.
	jr l14fch		;14f8	18 02		. .
l14fah:
	sbc hl,bc		;14fa	ed 42		. B
l14fch:
	call 0644dh		;14fc	cd 4d 64	. M d
	cpl			;14ff	2f		/
	ld b,a			;1500	47		G
	ex de,hl		;1501	eb		.
	call 0644dh		;1502	cd 4d 64	. M d
	cpl			;1505	2f		/
	ld c,a			;1506	4f		O
	xor b			;1507	a8		.
	jr z,l1520h		;1508	28 16		( .
	ld a,c			;150a	79		y
	and b			;150b	a0		.
	ld b,a			;150c	47		G
	ld c,000h		;150d	0e 00		. .
	scf			;150f	37		7
l1510h:
	ld a,b			;1510	78		x
	rl c			;1511	cb 11		. .
	and c			;1513	a1		.
	jr nz,l1510h		;1514	20 fa		  .
l1516h:
	ld a,b			;1516	78		x
	rl c			;1517	cb 11		. .
	and c			;1519	a1		.
	jr z,l1520h		;151a	28 04		( .
	xor b			;151c	a8		.
	ld b,a			;151d	47		G
	jr l1516h		;151e	18 f6		. .
l1520h:
	ld a,b			;1520	78		x
	ret			;1521	c9		.
	push af			;1522	f5		.
	push bc			;1523	c5		.
	push de			;1524	d5		.
	push hl			;1525	e5		.
	ld hl,l0000h		;1526	21 00 00	! . .
	add hl,sp		;1529	39		9
	ld de,l0008h+2		;152a	11 0a 00	. . .
	add hl,de		;152d	19		.
	ex de,hl		;152e	eb		.
	ld a,(06315h)		;152f	3a 15 63	: . c
	ld c,a			;1532	4f		O
	ld b,000h		;1533	06 00		. .
	ld hl,l0000h		;1535	21 00 00	! . .
	add hl,sp		;1538	39		9
	and a			;1539	a7		.
	sbc hl,bc		;153a	ed 42		. B
	dec hl			;153c	2b		+
	dec hl			;153d	2b		+
	push hl			;153e	e5		.
	pop ix			;153f	dd e1		. .
	ld sp,ix		;1541	dd f9		. .
	call 0651eh		;1543	cd 1e 65	. . e
	push de			;1546	d5		.
	pop ix			;1547	dd e1		. .
	ld l,(ix+006h)		;1549	dd 6e 06	. n .
	ld h,(ix+007h)		;154c	dd 66 07	. f .
	call 066e8h		;154f	cd e8 66	. . f
	push af			;1552	f5		.
	ld l,(ix+004h)		;1553	dd 6e 04	. n .
	ld h,(ix+005h)		;1556	dd 66 05	. f .
	call 066e8h		;1559	cd e8 66	. . f
	ld c,a			;155c	4f		O
	pop af			;155d	f1		.
	ld b,a			;155e	47		G
	ld a,(ix+009h)		;155f	dd 7e 09	. ~ .
	ld d,(ix+008h)		;1562	dd 56 08	. V .
	cp d			;1565	ba		.
	jr nz,l156dh		;1566	20 05		  .
	ld a,b			;1568	78		x
	and c			;1569	a1		.
	ld b,a			;156a	47		G
	jr l1578h		;156b	18 0b		. .
l156dh:
	ld a,b			;156d	78		x
	or c			;156e	b1		.
	cp 0ffh			;156f	fe ff		. .
	jr nz,l15a0h		;1571	20 2d		  -
	ld e,b			;1573	58		X
	ld b,d			;1574	42		B
	call 06499h		;1575	cd 99 64	. . d
l1578h:
	ld b,(ix+009h)		;1578	dd 46 09	. F .
	ld c,e			;157b	4b		K
	call 06499h		;157c	cd 99 64	. . d
	ld l,(ix+006h)		;157f	dd 6e 06	. n .
	ld h,(ix+007h)		;1582	dd 66 07	. f .
	ld e,(ix+004h)		;1585	dd 5e 04	. ^ .
	ld d,(ix+005h)		;1588	dd 56 05	. V .
	ld c,(ix+002h)		;158b	dd 4e 02	. N .
	ld b,(ix+003h)		;158e	dd 46 03	. F .
	ld a,(ix+000h)		;1591	dd 7e 00	. ~ .
	rlca			;1594	07		.
	rrca			;1595	0f		.
	jr c,l159ch		;1596	38 04		8 .
	ldir			;1598	ed b0		. .
	jr l15eeh		;159a	18 52		. R
l159ch:
	lddr			;159c	ed b8		. .
	jr l15eeh		;159e	18 4e		. N
l15a0h:
	ld hl,05cc0h		;15a0	21 c0 5c	! . \
	push bc			;15a3	c5		.
	ld b,0ffh		;15a4	06 ff		. .
	call 06316h		;15a6	cd 16 63	. . c
	pop bc			;15a9	c1		.
	ld de,00200h		;15aa	11 00 02	. . .
	and a			;15ad	a7		.
	sbc hl,de		;15ae	ed 52		. R
	ld de,l0020h		;15b0	11 20 00	.   .
	add hl,de		;15b3	19		.
	ex de,hl		;15b4	eb		.
	ld hl,l0000h		;15b5	21 00 00	! . .
	add hl,sp		;15b8	39		9
	inc de			;15b9	13		.
	and a			;15ba	a7		.
	sbc hl,de		;15bb	ed 52		. R
	jr nc,l15c3h		;15bd	30 04		0 .
	ld a,001h		;15bf	3e 01		> .
	jr l15eeh		;15c1	18 2b		. +
l15c3h:
	dec de			;15c3	1b		.
	ex de,hl		;15c4	eb		.
	ld sp,hl		;15c5	f9		.
	inc de			;15c6	13		.
	ld a,(ix+000h)		;15c7	dd 7e 00	. ~ .
	ld (ix+000h),l		;15ca	dd 75 00	. u .
	ld (ix+001h),h		;15cd	dd 74 01	. t .
	ld l,(ix+002h)		;15d0	dd 6e 02	. n .
	ld h,(ix+003h)		;15d3	dd 66 03	. f .
l15d6h:
	and a			;15d6	a7		.
	sbc hl,de		;15d7	ed 52		. R
	jr c,l15e0h		;15d9	38 05		8 .
	call 0668ch		;15db	cd 8c 66	. . f
	jr l15d6h		;15de	18 f6		. .
l15e0h:
	add hl,de		;15e0	19		.
	ex de,hl		;15e1	eb		.
	call 0668ch		;15e2	cd 8c 66	. . f
	ex de,hl		;15e5	eb		.
	ld l,(ix+000h)		;15e6	dd 6e 00	. n .
	ld h,(ix+001h)		;15e9	dd 66 01	. f .
	add hl,de		;15ec	19		.
	ld sp,hl		;15ed	f9		.
l15eeh:
	xor a			;15ee	af		.
	ld ix,l0000h		;15ef	dd 21 00 00	. ! . .
	add ix,sp		;15f3	dd 39		. 9
	call 0654ah		;15f5	cd 4a 65	. J e
	inc ix			;15f8	dd 23		. #
	ld sp,ix		;15fa	dd f9		. .
	pop hl			;15fc	e1		.
	pop de			;15fd	d1		.
	pop bc			;15fe	c1		.
	pop af			;15ff	f1		.
	pop ix			;1600	dd e1		. .
	ex (sp),ix		;1602	dd e3		. .
	pop ix			;1604	dd e1		. .
	ex (sp),ix		;1606	dd e3		. .
	pop ix			;1608	dd e1		. .
	ex (sp),ix		;160a	dd e3		. .
	pop ix			;160c	dd e1		. .
	ex (sp),ix		;160e	dd e3		. .
	pop ix			;1610	dd e1		. .
	ex (sp),ix		;1612	dd e3		. .
	ret			;1614	c9		.
	pop ix			;1615	dd e1		. .
	push af			;1617	f5		.
	in a,(0ffh)		;1618	db ff		. .
	set 7,a			;161a	cb ff		. .
	out (0ffh),a		;161c	d3 ff		. .
	ld a,001h		;161e	3e 01		> .
	out (0f4h),a		;1620	d3 f4		. .
	pop af			;1622	f1		.
	jp (hl)			;1623	e9		.
	nop			;1624	00		.
	nop			;1625	00		.
	nop			;1626	00		.
	nop			;1627	00		.
	nop			;1628	00		.
	nop			;1629	00		.
	nop			;162a	00		.
	nop			;162b	00		.
	nop			;162c	00		.
	nop			;162d	00		.
	nop			;162e	00		.
	nop			;162f	00		.
	nop			;1630	00		.
	nop			;1631	00		.
	nop			;1632	00		.
	nop			;1633	00		.
	nop			;1634	00		.
	nop			;1635	00		.
	nop			;1636	00		.
	nop			;1637	00		.
	nop			;1638	00		.
	nop			;1639	00		.
	nop			;163a	00		.
	nop			;163b	00		.
	nop			;163c	00		.
	nop			;163d	00		.
	nop			;163e	00		.
	nop			;163f	00		.
	nop			;1640	00		.
	nop			;1641	00		.
	nop			;1642	00		.
	nop			;1643	00		.
	nop			;1644	00		.
	nop			;1645	00		.
	nop			;1646	00		.
	nop			;1647	00		.
	nop			;1648	00		.
	nop			;1649	00		.
	nop			;164a	00		.
	nop			;164b	00		.
	nop			;164c	00		.
	nop			;164d	00		.
	nop			;164e	00		.
	nop			;164f	00		.
	nop			;1650	00		.
	nop			;1651	00		.
	nop			;1652	00		.
	nop			;1653	00		.
	nop			;1654	00		.
	nop			;1655	00		.
	nop			;1656	00		.
	nop			;1657	00		.
	nop			;1658	00		.
	nop			;1659	00		.
	nop			;165a	00		.
	nop			;165b	00		.
	nop			;165c	00		.
	nop			;165d	00		.
	nop			;165e	00		.
	nop			;165f	00		.
	nop			;1660	00		.
	nop			;1661	00		.
	nop			;1662	00		.
	nop			;1663	00		.
	nop			;1664	00		.
	nop			;1665	00		.
	nop			;1666	00		.
	nop			;1667	00		.
	nop			;1668	00		.
	nop			;1669	00		.
	nop			;166a	00		.
	nop			;166b	00		.
	nop			;166c	00		.
	nop			;166d	00		.
	nop			;166e	00		.
	nop			;166f	00		.
	nop			;1670	00		.
	nop			;1671	00		.
	nop			;1672	00		.
	nop			;1673	00		.
	nop			;1674	00		.
	nop			;1675	00		.
	nop			;1676	00		.
	nop			;1677	00		.
	nop			;1678	00		.
	nop			;1679	00		.
	nop			;167a	00		.
	nop			;167b	00		.
	nop			;167c	00		.
	nop			;167d	00		.
	nop			;167e	00		.
	nop			;167f	00		.
	nop			;1680	00		.
	nop			;1681	00		.
	nop			;1682	00		.
	nop			;1683	00		.
	nop			;1684	00		.
	nop			;1685	00		.
	nop			;1686	00		.
	nop			;1687	00		.
	nop			;1688	00		.
	nop			;1689	00		.
	nop			;168a	00		.
	nop			;168b	00		.
	nop			;168c	00		.
	nop			;168d	00		.
	nop			;168e	00		.
	nop			;168f	00		.
	nop			;1690	00		.
	nop			;1691	00		.
	nop			;1692	00		.
	nop			;1693	00		.
	nop			;1694	00		.
	nop			;1695	00		.
	nop			;1696	00		.
	nop			;1697	00		.
	nop			;1698	00		.
	nop			;1699	00		.
	nop			;169a	00		.
	nop			;169b	00		.
	nop			;169c	00		.
	nop			;169d	00		.
	nop			;169e	00		.
	nop			;169f	00		.
	nop			;16a0	00		.
	nop			;16a1	00		.
	nop			;16a2	00		.
	nop			;16a3	00		.
	nop			;16a4	00		.
	nop			;16a5	00		.
	nop			;16a6	00		.
	nop			;16a7	00		.
	nop			;16a8	00		.
	nop			;16a9	00		.
	nop			;16aa	00		.
	nop			;16ab	00		.
	nop			;16ac	00		.
	nop			;16ad	00		.
	nop			;16ae	00		.
	nop			;16af	00		.
	nop			;16b0	00		.
	nop			;16b1	00		.
	nop			;16b2	00		.
	nop			;16b3	00		.
	nop			;16b4	00		.
	nop			;16b5	00		.
	nop			;16b6	00		.
	nop			;16b7	00		.
	nop			;16b8	00		.
	nop			;16b9	00		.
	nop			;16ba	00		.
	nop			;16bb	00		.
	nop			;16bc	00		.
	nop			;16bd	00		.
	nop			;16be	00		.
	nop			;16bf	00		.
	nop			;16c0	00		.
	nop			;16c1	00		.
	nop			;16c2	00		.
	nop			;16c3	00		.
	nop			;16c4	00		.
	nop			;16c5	00		.
	nop			;16c6	00		.
	nop			;16c7	00		.
	nop			;16c8	00		.
	nop			;16c9	00		.
	nop			;16ca	00		.
	nop			;16cb	00		.
	nop			;16cc	00		.
	nop			;16cd	00		.
	nop			;16ce	00		.
	nop			;16cf	00		.
	nop			;16d0	00		.
	nop			;16d1	00		.
	nop			;16d2	00		.
	nop			;16d3	00		.
	nop			;16d4	00		.
	nop			;16d5	00		.
	nop			;16d6	00		.
	nop			;16d7	00		.
	nop			;16d8	00		.
	nop			;16d9	00		.
	nop			;16da	00		.
	nop			;16db	00		.
	nop			;16dc	00		.
	nop			;16dd	00		.
	nop			;16de	00		.
	nop			;16df	00		.
	nop			;16e0	00		.
	nop			;16e1	00		.
	nop			;16e2	00		.
	nop			;16e3	00		.
	nop			;16e4	00		.
	nop			;16e5	00		.
	nop			;16e6	00		.
	nop			;16e7	00		.
	nop			;16e8	00		.
	nop			;16e9	00		.
	nop			;16ea	00		.
	nop			;16eb	00		.
	nop			;16ec	00		.
	nop			;16ed	00		.
	nop			;16ee	00		.
	nop			;16ef	00		.
	nop			;16f0	00		.
	nop			;16f1	00		.
	nop			;16f2	00		.
	nop			;16f3	00		.
	nop			;16f4	00		.
	nop			;16f5	00		.
	nop			;16f6	00		.
	nop			;16f7	00		.
	nop			;16f8	00		.
	nop			;16f9	00		.
	nop			;16fa	00		.
	nop			;16fb	00		.
	nop			;16fc	00		.
	nop			;16fd	00		.
	nop			;16fe	00		.
	nop			;16ff	00		.
	nop			;1700	00		.
	nop			;1701	00		.
	nop			;1702	00		.
	nop			;1703	00		.
	nop			;1704	00		.
	nop			;1705	00		.
	nop			;1706	00		.
	nop			;1707	00		.
	nop			;1708	00		.
	nop			;1709	00		.
	nop			;170a	00		.
	nop			;170b	00		.
	nop			;170c	00		.
	nop			;170d	00		.
	nop			;170e	00		.
	nop			;170f	00		.
	nop			;1710	00		.
	nop			;1711	00		.
	nop			;1712	00		.
	nop			;1713	00		.
	nop			;1714	00		.
	nop			;1715	00		.
	nop			;1716	00		.
	nop			;1717	00		.
	nop			;1718	00		.
	nop			;1719	00		.
	nop			;171a	00		.
	nop			;171b	00		.
	nop			;171c	00		.
	nop			;171d	00		.
	nop			;171e	00		.
	nop			;171f	00		.
l1720h:
	nop			;1720	00		.
	nop			;1721	00		.
	nop			;1722	00		.
	nop			;1723	00		.
	nop			;1724	00		.
	nop			;1725	00		.
	nop			;1726	00		.
	nop			;1727	00		.
	nop			;1728	00		.
	nop			;1729	00		.
	nop			;172a	00		.
	nop			;172b	00		.
	nop			;172c	00		.
	nop			;172d	00		.
	nop			;172e	00		.
	nop			;172f	00		.
	nop			;1730	00		.
	nop			;1731	00		.
	nop			;1732	00		.
	nop			;1733	00		.
	nop			;1734	00		.
	nop			;1735	00		.
	nop			;1736	00		.
	nop			;1737	00		.
	nop			;1738	00		.
	nop			;1739	00		.
	nop			;173a	00		.
	nop			;173b	00		.
	nop			;173c	00		.
	nop			;173d	00		.
	nop			;173e	00		.
	nop			;173f	00		.
	nop			;1740	00		.
	nop			;1741	00		.
	nop			;1742	00		.
	nop			;1743	00		.
	nop			;1744	00		.
	nop			;1745	00		.
	nop			;1746	00		.
	nop			;1747	00		.
	nop			;1748	00		.
	nop			;1749	00		.
	nop			;174a	00		.
	nop			;174b	00		.
	nop			;174c	00		.
l174dh:
	nop			;174d	00		.
	nop			;174e	00		.
	add a,b			;174f	80		.
l1750h:
	nop			;1750	00		.
	nop			;1751	00		.
	nop			;1752	00		.
	nop			;1753	00		.
	nop			;1754	00		.
	nop			;1755	00		.
	nop			;1756	00		.
	nop			;1757	00		.
	nop			;1758	00		.
	nop			;1759	00		.
	nop			;175a	00		.
	nop			;175b	00		.
	nop			;175c	00		.
	nop			;175d	00		.
	nop			;175e	00		.
	nop			;175f	00		.
	nop			;1760	00		.
	nop			;1761	00		.
	nop			;1762	00		.
	nop			;1763	00		.
	nop			;1764	00		.
	nop			;1765	00		.
	nop			;1766	00		.
	nop			;1767	00		.
	nop			;1768	00		.
	nop			;1769	00		.
	nop			;176a	00		.
	nop			;176b	00		.
	nop			;176c	00		.
	nop			;176d	00		.
	nop			;176e	00		.
	nop			;176f	00		.
	nop			;1770	00		.
	nop			;1771	00		.
	nop			;1772	00		.
	nop			;1773	00		.
	nop			;1774	00		.
	nop			;1775	00		.
	nop			;1776	00		.
	nop			;1777	00		.
	nop			;1778	00		.
	nop			;1779	00		.
	nop			;177a	00		.
	nop			;177b	00		.
	nop			;177c	00		.
	nop			;177d	00		.
	nop			;177e	00		.
	nop			;177f	00		.
	nop			;1780	00		.
	nop			;1781	00		.
	nop			;1782	00		.
	nop			;1783	00		.
	nop			;1784	00		.
	nop			;1785	00		.
	nop			;1786	00		.
	nop			;1787	00		.
	nop			;1788	00		.
	nop			;1789	00		.
	nop			;178a	00		.
	nop			;178b	00		.
	nop			;178c	00		.
	nop			;178d	00		.
	nop			;178e	00		.
	nop			;178f	00		.
	nop			;1790	00		.
	nop			;1791	00		.
	nop			;1792	00		.
	nop			;1793	00		.
	nop			;1794	00		.
	nop			;1795	00		.
	nop			;1796	00		.
	nop			;1797	00		.
	nop			;1798	00		.
	nop			;1799	00		.
	nop			;179a	00		.
	nop			;179b	00		.
	nop			;179c	00		.
	nop			;179d	00		.
	nop			;179e	00		.
	nop			;179f	00		.
	nop			;17a0	00		.
	nop			;17a1	00		.
	nop			;17a2	00		.
	nop			;17a3	00		.
	nop			;17a4	00		.
	nop			;17a5	00		.
	nop			;17a6	00		.
	nop			;17a7	00		.
	nop			;17a8	00		.
	nop			;17a9	00		.
	nop			;17aa	00		.
	nop			;17ab	00		.
	nop			;17ac	00		.
	nop			;17ad	00		.
	nop			;17ae	00		.
	nop			;17af	00		.
	nop			;17b0	00		.
	nop			;17b1	00		.
	nop			;17b2	00		.
	nop			;17b3	00		.
	nop			;17b4	00		.
	nop			;17b5	00		.
	nop			;17b6	00		.
	nop			;17b7	00		.
	nop			;17b8	00		.
	nop			;17b9	00		.
	nop			;17ba	00		.
	nop			;17bb	00		.
	nop			;17bc	00		.
	nop			;17bd	00		.
	nop			;17be	00		.
	nop			;17bf	00		.
	nop			;17c0	00		.
	nop			;17c1	00		.
	nop			;17c2	00		.
	nop			;17c3	00		.
	nop			;17c4	00		.
	nop			;17c5	00		.
	nop			;17c6	00		.
	nop			;17c7	00		.
	nop			;17c8	00		.
	nop			;17c9	00		.
	nop			;17ca	00		.
	nop			;17cb	00		.
	nop			;17cc	00		.
	nop			;17cd	00		.
	nop			;17ce	00		.
	nop			;17cf	00		.
	nop			;17d0	00		.
	nop			;17d1	00		.
	nop			;17d2	00		.
	nop			;17d3	00		.
	nop			;17d4	00		.
	nop			;17d5	00		.
	nop			;17d6	00		.
	nop			;17d7	00		.
	nop			;17d8	00		.
	nop			;17d9	00		.
	nop			;17da	00		.
	nop			;17db	00		.
	nop			;17dc	00		.
	nop			;17dd	00		.
	nop			;17de	00		.
	nop			;17df	00		.
	nop			;17e0	00		.
	nop			;17e1	00		.
	nop			;17e2	00		.
	nop			;17e3	00		.
	nop			;17e4	00		.
	nop			;17e5	00		.
	nop			;17e6	00		.
	nop			;17e7	00		.
	nop			;17e8	00		.
	nop			;17e9	00		.
	nop			;17ea	00		.
	nop			;17eb	00		.
	nop			;17ec	00		.
	nop			;17ed	00		.
	nop			;17ee	00		.
	nop			;17ef	00		.
	nop			;17f0	00		.
	nop			;17f1	00		.
	nop			;17f2	00		.
	nop			;17f3	00		.
	nop			;17f4	00		.
	nop			;17f5	00		.
	nop			;17f6	00		.
	nop			;17f7	00		.
	nop			;17f8	00		.
	nop			;17f9	00		.
	nop			;17fa	00		.
	nop			;17fb	00		.
	nop			;17fc	00		.
	nop			;17fd	00		.
	nop			;17fe	00		.
	nop			;17ff	00		.
	rst 38h			;1800	ff		.
	rst 38h			;1801	ff		.
	rst 38h			;1802	ff		.
	rst 38h			;1803	ff		.
	rst 38h			;1804	ff		.
	rst 38h			;1805	ff		.
	rst 38h			;1806	ff		.
	rst 38h			;1807	ff		.
	rst 38h			;1808	ff		.
	rst 38h			;1809	ff		.
	rst 38h			;180a	ff		.
	rst 38h			;180b	ff		.
	rst 38h			;180c	ff		.
	rst 38h			;180d	ff		.
	rst 38h			;180e	ff		.
	rst 38h			;180f	ff		.
	rst 38h			;1810	ff		.
	rst 38h			;1811	ff		.
	rst 38h			;1812	ff		.
	rst 38h			;1813	ff		.
	rst 38h			;1814	ff		.
	rst 38h			;1815	ff		.
	rst 38h			;1816	ff		.
	rst 38h			;1817	ff		.
	rst 38h			;1818	ff		.
	rst 38h			;1819	ff		.
	rst 38h			;181a	ff		.
	rst 38h			;181b	ff		.
	rst 38h			;181c	ff		.
	rst 38h			;181d	ff		.
	rst 38h			;181e	ff		.
	rst 38h			;181f	ff		.
	rst 38h			;1820	ff		.
	rst 38h			;1821	ff		.
	rst 38h			;1822	ff		.
	rst 38h			;1823	ff		.
	rst 38h			;1824	ff		.
	rst 38h			;1825	ff		.
	rst 38h			;1826	ff		.
	rst 38h			;1827	ff		.
	rst 38h			;1828	ff		.
	rst 38h			;1829	ff		.
	rst 38h			;182a	ff		.
	rst 38h			;182b	ff		.
	rst 38h			;182c	ff		.
	rst 38h			;182d	ff		.
	rst 38h			;182e	ff		.
	rst 38h			;182f	ff		.
	rst 38h			;1830	ff		.
	rst 38h			;1831	ff		.
	rst 38h			;1832	ff		.
	rst 38h			;1833	ff		.
	rst 38h			;1834	ff		.
	rst 38h			;1835	ff		.
	rst 38h			;1836	ff		.
	rst 38h			;1837	ff		.
	rst 38h			;1838	ff		.
	rst 38h			;1839	ff		.
	rst 38h			;183a	ff		.
	rst 38h			;183b	ff		.
	rst 38h			;183c	ff		.
	rst 38h			;183d	ff		.
	rst 38h			;183e	ff		.
	rst 38h			;183f	ff		.
	rst 38h			;1840	ff		.
	rst 38h			;1841	ff		.
	rst 38h			;1842	ff		.
	rst 38h			;1843	ff		.
	rst 38h			;1844	ff		.
	rst 38h			;1845	ff		.
	rst 38h			;1846	ff		.
	rst 38h			;1847	ff		.
	rst 38h			;1848	ff		.
	rst 38h			;1849	ff		.
	rst 38h			;184a	ff		.
	rst 38h			;184b	ff		.
	rst 38h			;184c	ff		.
	rst 38h			;184d	ff		.
	rst 38h			;184e	ff		.
	rst 38h			;184f	ff		.
	rst 38h			;1850	ff		.
	rst 38h			;1851	ff		.
	rst 38h			;1852	ff		.
	rst 38h			;1853	ff		.
	rst 38h			;1854	ff		.
	rst 38h			;1855	ff		.
	rst 38h			;1856	ff		.
	rst 38h			;1857	ff		.
	rst 38h			;1858	ff		.
	rst 38h			;1859	ff		.
	rst 38h			;185a	ff		.
	rst 38h			;185b	ff		.
	rst 38h			;185c	ff		.
	rst 38h			;185d	ff		.
	rst 38h			;185e	ff		.
	rst 38h			;185f	ff		.
	rst 38h			;1860	ff		.
	rst 38h			;1861	ff		.
	rst 38h			;1862	ff		.
	rst 38h			;1863	ff		.
	rst 38h			;1864	ff		.
	rst 38h			;1865	ff		.
	rst 38h			;1866	ff		.
	rst 38h			;1867	ff		.
	rst 38h			;1868	ff		.
	rst 38h			;1869	ff		.
	rst 38h			;186a	ff		.
	rst 38h			;186b	ff		.
	rst 38h			;186c	ff		.
	rst 38h			;186d	ff		.
	rst 38h			;186e	ff		.
	rst 38h			;186f	ff		.
	rst 38h			;1870	ff		.
	rst 38h			;1871	ff		.
	rst 38h			;1872	ff		.
	rst 38h			;1873	ff		.
	rst 38h			;1874	ff		.
	rst 38h			;1875	ff		.
	rst 38h			;1876	ff		.
	rst 38h			;1877	ff		.
	rst 38h			;1878	ff		.
	rst 38h			;1879	ff		.
	rst 38h			;187a	ff		.
	rst 38h			;187b	ff		.
	rst 38h			;187c	ff		.
	rst 38h			;187d	ff		.
	rst 38h			;187e	ff		.
	rst 38h			;187f	ff		.
	rst 38h			;1880	ff		.
	rst 38h			;1881	ff		.
	rst 38h			;1882	ff		.
	rst 38h			;1883	ff		.
	rst 38h			;1884	ff		.
	rst 38h			;1885	ff		.
	rst 38h			;1886	ff		.
	rst 38h			;1887	ff		.
	rst 38h			;1888	ff		.
	rst 38h			;1889	ff		.
	rst 38h			;188a	ff		.
	rst 38h			;188b	ff		.
	rst 38h			;188c	ff		.
	rst 38h			;188d	ff		.
	rst 38h			;188e	ff		.
	rst 38h			;188f	ff		.
	rst 38h			;1890	ff		.
	rst 38h			;1891	ff		.
	rst 38h			;1892	ff		.
	rst 38h			;1893	ff		.
	rst 38h			;1894	ff		.
	rst 38h			;1895	ff		.
	rst 38h			;1896	ff		.
	rst 38h			;1897	ff		.
	rst 38h			;1898	ff		.
	rst 38h			;1899	ff		.
	rst 38h			;189a	ff		.
	rst 38h			;189b	ff		.
	rst 38h			;189c	ff		.
	rst 38h			;189d	ff		.
	rst 38h			;189e	ff		.
	rst 38h			;189f	ff		.
	rst 38h			;18a0	ff		.
	rst 38h			;18a1	ff		.
	rst 38h			;18a2	ff		.
	rst 38h			;18a3	ff		.
	rst 38h			;18a4	ff		.
	rst 38h			;18a5	ff		.
	rst 38h			;18a6	ff		.
	rst 38h			;18a7	ff		.
	rst 38h			;18a8	ff		.
	rst 38h			;18a9	ff		.
	rst 38h			;18aa	ff		.
	rst 38h			;18ab	ff		.
	rst 38h			;18ac	ff		.
	rst 38h			;18ad	ff		.
	rst 38h			;18ae	ff		.
	rst 38h			;18af	ff		.
	rst 38h			;18b0	ff		.
	rst 38h			;18b1	ff		.
	rst 38h			;18b2	ff		.
	rst 38h			;18b3	ff		.
	rst 38h			;18b4	ff		.
	rst 38h			;18b5	ff		.
	rst 38h			;18b6	ff		.
	rst 38h			;18b7	ff		.
	rst 38h			;18b8	ff		.
	rst 38h			;18b9	ff		.
	rst 38h			;18ba	ff		.
	rst 38h			;18bb	ff		.
	rst 38h			;18bc	ff		.
	rst 38h			;18bd	ff		.
	rst 38h			;18be	ff		.
	rst 38h			;18bf	ff		.
	rst 38h			;18c0	ff		.
	rst 38h			;18c1	ff		.
	rst 38h			;18c2	ff		.
	rst 38h			;18c3	ff		.
	rst 38h			;18c4	ff		.
	rst 38h			;18c5	ff		.
l18c6h:
	rst 38h			;18c6	ff		.
	rst 38h			;18c7	ff		.
	rst 38h			;18c8	ff		.
	rst 38h			;18c9	ff		.
	rst 38h			;18ca	ff		.
	rst 38h			;18cb	ff		.
	rst 38h			;18cc	ff		.
	rst 38h			;18cd	ff		.
	rst 38h			;18ce	ff		.
	rst 38h			;18cf	ff		.
	rst 38h			;18d0	ff		.
	rst 38h			;18d1	ff		.
	rst 38h			;18d2	ff		.
	rst 38h			;18d3	ff		.
	rst 38h			;18d4	ff		.
	rst 38h			;18d5	ff		.
	rst 38h			;18d6	ff		.
	rst 38h			;18d7	ff		.
	rst 38h			;18d8	ff		.
	rst 38h			;18d9	ff		.
	rst 38h			;18da	ff		.
	rst 38h			;18db	ff		.
	rst 38h			;18dc	ff		.
	rst 38h			;18dd	ff		.
	rst 38h			;18de	ff		.
	rst 38h			;18df	ff		.
	rst 38h			;18e0	ff		.
	rst 38h			;18e1	ff		.
	rst 38h			;18e2	ff		.
	rst 38h			;18e3	ff		.
	rst 38h			;18e4	ff		.
	rst 38h			;18e5	ff		.
	rst 38h			;18e6	ff		.
	rst 38h			;18e7	ff		.
	rst 38h			;18e8	ff		.
	rst 38h			;18e9	ff		.
	rst 38h			;18ea	ff		.
	rst 38h			;18eb	ff		.
	rst 38h			;18ec	ff		.
	rst 38h			;18ed	ff		.
	rst 38h			;18ee	ff		.
	rst 38h			;18ef	ff		.
	rst 38h			;18f0	ff		.
	rst 38h			;18f1	ff		.
	rst 38h			;18f2	ff		.
	rst 38h			;18f3	ff		.
	rst 38h			;18f4	ff		.
	rst 38h			;18f5	ff		.
	rst 38h			;18f6	ff		.
	rst 38h			;18f7	ff		.
	rst 38h			;18f8	ff		.
	rst 38h			;18f9	ff		.
	rst 38h			;18fa	ff		.
	rst 38h			;18fb	ff		.
	rst 38h			;18fc	ff		.
	rst 38h			;18fd	ff		.
	rst 38h			;18fe	ff		.
	rst 38h			;18ff	ff		.
	rst 38h			;1900	ff		.
	rst 38h			;1901	ff		.
	rst 38h			;1902	ff		.
	rst 38h			;1903	ff		.
	rst 38h			;1904	ff		.
	rst 38h			;1905	ff		.
	rst 38h			;1906	ff		.
	rst 38h			;1907	ff		.
	rst 38h			;1908	ff		.
	rst 38h			;1909	ff		.
	rst 38h			;190a	ff		.
	rst 38h			;190b	ff		.
	rst 38h			;190c	ff		.
	rst 38h			;190d	ff		.
	rst 38h			;190e	ff		.
	rst 38h			;190f	ff		.
	rst 38h			;1910	ff		.
	rst 38h			;1911	ff		.
	rst 38h			;1912	ff		.
	rst 38h			;1913	ff		.
	rst 38h			;1914	ff		.
	rst 38h			;1915	ff		.
	rst 38h			;1916	ff		.
	rst 38h			;1917	ff		.
	rst 38h			;1918	ff		.
	rst 38h			;1919	ff		.
	rst 38h			;191a	ff		.
	rst 38h			;191b	ff		.
	rst 38h			;191c	ff		.
	rst 38h			;191d	ff		.
	rst 38h			;191e	ff		.
	rst 38h			;191f	ff		.
	rst 38h			;1920	ff		.
	rst 38h			;1921	ff		.
	rst 38h			;1922	ff		.
	rst 38h			;1923	ff		.
	rst 38h			;1924	ff		.
	rst 38h			;1925	ff		.
	rst 38h			;1926	ff		.
	rst 38h			;1927	ff		.
	rst 38h			;1928	ff		.
	rst 38h			;1929	ff		.
	rst 38h			;192a	ff		.
	rst 38h			;192b	ff		.
	rst 38h			;192c	ff		.
	rst 38h			;192d	ff		.
	rst 38h			;192e	ff		.
	rst 38h			;192f	ff		.
	rst 38h			;1930	ff		.
	rst 38h			;1931	ff		.
	rst 38h			;1932	ff		.
	rst 38h			;1933	ff		.
	rst 38h			;1934	ff		.
	rst 38h			;1935	ff		.
	rst 38h			;1936	ff		.
	rst 38h			;1937	ff		.
	rst 38h			;1938	ff		.
	rst 38h			;1939	ff		.
	rst 38h			;193a	ff		.
	rst 38h			;193b	ff		.
	rst 38h			;193c	ff		.
	rst 38h			;193d	ff		.
	rst 38h			;193e	ff		.
	rst 38h			;193f	ff		.
	rst 38h			;1940	ff		.
	rst 38h			;1941	ff		.
	rst 38h			;1942	ff		.
	rst 38h			;1943	ff		.
	rst 38h			;1944	ff		.
	rst 38h			;1945	ff		.
	rst 38h			;1946	ff		.
	rst 38h			;1947	ff		.
	rst 38h			;1948	ff		.
	rst 38h			;1949	ff		.
	rst 38h			;194a	ff		.
	rst 38h			;194b	ff		.
	rst 38h			;194c	ff		.
	rst 38h			;194d	ff		.
	rst 38h			;194e	ff		.
	rst 38h			;194f	ff		.
	rst 38h			;1950	ff		.
	rst 38h			;1951	ff		.
	rst 38h			;1952	ff		.
	rst 38h			;1953	ff		.
	rst 38h			;1954	ff		.
	rst 38h			;1955	ff		.
	rst 38h			;1956	ff		.
	rst 38h			;1957	ff		.
	rst 38h			;1958	ff		.
	rst 38h			;1959	ff		.
	rst 38h			;195a	ff		.
	rst 38h			;195b	ff		.
	rst 38h			;195c	ff		.
	rst 38h			;195d	ff		.
	rst 38h			;195e	ff		.
	rst 38h			;195f	ff		.
	rst 38h			;1960	ff		.
	rst 38h			;1961	ff		.
	rst 38h			;1962	ff		.
	rst 38h			;1963	ff		.
	rst 38h			;1964	ff		.
	rst 38h			;1965	ff		.
	rst 38h			;1966	ff		.
	rst 38h			;1967	ff		.
	rst 38h			;1968	ff		.
	rst 38h			;1969	ff		.
	rst 38h			;196a	ff		.
	rst 38h			;196b	ff		.
	rst 38h			;196c	ff		.
	rst 38h			;196d	ff		.
	rst 38h			;196e	ff		.
	rst 38h			;196f	ff		.
	rst 38h			;1970	ff		.
	rst 38h			;1971	ff		.
	rst 38h			;1972	ff		.
	rst 38h			;1973	ff		.
	rst 38h			;1974	ff		.
	rst 38h			;1975	ff		.
	rst 38h			;1976	ff		.
	rst 38h			;1977	ff		.
	rst 38h			;1978	ff		.
	rst 38h			;1979	ff		.
	rst 38h			;197a	ff		.
	rst 38h			;197b	ff		.
	rst 38h			;197c	ff		.
	rst 38h			;197d	ff		.
	rst 38h			;197e	ff		.
	rst 38h			;197f	ff		.
	rst 38h			;1980	ff		.
	rst 38h			;1981	ff		.
	rst 38h			;1982	ff		.
	rst 38h			;1983	ff		.
	rst 38h			;1984	ff		.
	rst 38h			;1985	ff		.
	rst 38h			;1986	ff		.
	rst 38h			;1987	ff		.
	rst 38h			;1988	ff		.
	rst 38h			;1989	ff		.
	rst 38h			;198a	ff		.
	rst 38h			;198b	ff		.
	rst 38h			;198c	ff		.
	rst 38h			;198d	ff		.
	rst 38h			;198e	ff		.
	rst 38h			;198f	ff		.
	rst 38h			;1990	ff		.
	rst 38h			;1991	ff		.
	rst 38h			;1992	ff		.
	rst 38h			;1993	ff		.
	rst 38h			;1994	ff		.
	rst 38h			;1995	ff		.
	rst 38h			;1996	ff		.
	rst 38h			;1997	ff		.
	rst 38h			;1998	ff		.
	rst 38h			;1999	ff		.
	rst 38h			;199a	ff		.
	rst 38h			;199b	ff		.
	rst 38h			;199c	ff		.
	rst 38h			;199d	ff		.
	rst 38h			;199e	ff		.
	rst 38h			;199f	ff		.
	rst 38h			;19a0	ff		.
	rst 38h			;19a1	ff		.
	rst 38h			;19a2	ff		.
	rst 38h			;19a3	ff		.
	rst 38h			;19a4	ff		.
	rst 38h			;19a5	ff		.
	rst 38h			;19a6	ff		.
	rst 38h			;19a7	ff		.
	rst 38h			;19a8	ff		.
	rst 38h			;19a9	ff		.
	rst 38h			;19aa	ff		.
	rst 38h			;19ab	ff		.
	rst 38h			;19ac	ff		.
	rst 38h			;19ad	ff		.
	rst 38h			;19ae	ff		.
	rst 38h			;19af	ff		.
	rst 38h			;19b0	ff		.
	rst 38h			;19b1	ff		.
	rst 38h			;19b2	ff		.
	rst 38h			;19b3	ff		.
	rst 38h			;19b4	ff		.
	rst 38h			;19b5	ff		.
	rst 38h			;19b6	ff		.
	rst 38h			;19b7	ff		.
	rst 38h			;19b8	ff		.
	rst 38h			;19b9	ff		.
	rst 38h			;19ba	ff		.
	rst 38h			;19bb	ff		.
	rst 38h			;19bc	ff		.
	rst 38h			;19bd	ff		.
	rst 38h			;19be	ff		.
	rst 38h			;19bf	ff		.
	rst 38h			;19c0	ff		.
	rst 38h			;19c1	ff		.
	rst 38h			;19c2	ff		.
	rst 38h			;19c3	ff		.
	rst 38h			;19c4	ff		.
	rst 38h			;19c5	ff		.
	rst 38h			;19c6	ff		.
	rst 38h			;19c7	ff		.
	rst 38h			;19c8	ff		.
	rst 38h			;19c9	ff		.
	rst 38h			;19ca	ff		.
	rst 38h			;19cb	ff		.
	rst 38h			;19cc	ff		.
	rst 38h			;19cd	ff		.
	rst 38h			;19ce	ff		.
	rst 38h			;19cf	ff		.
	rst 38h			;19d0	ff		.
	rst 38h			;19d1	ff		.
	rst 38h			;19d2	ff		.
	rst 38h			;19d3	ff		.
	rst 38h			;19d4	ff		.
	rst 38h			;19d5	ff		.
	rst 38h			;19d6	ff		.
	rst 38h			;19d7	ff		.
	rst 38h			;19d8	ff		.
	rst 38h			;19d9	ff		.
	rst 38h			;19da	ff		.
	rst 38h			;19db	ff		.
	rst 38h			;19dc	ff		.
	rst 38h			;19dd	ff		.
	rst 38h			;19de	ff		.
	rst 38h			;19df	ff		.
	rst 38h			;19e0	ff		.
l19e1h:
	rst 38h			;19e1	ff		.
	rst 38h			;19e2	ff		.
	rst 38h			;19e3	ff		.
	rst 38h			;19e4	ff		.
	rst 38h			;19e5	ff		.
	rst 38h			;19e6	ff		.
	rst 38h			;19e7	ff		.
	rst 38h			;19e8	ff		.
	rst 38h			;19e9	ff		.
	rst 38h			;19ea	ff		.
	rst 38h			;19eb	ff		.
	rst 38h			;19ec	ff		.
	rst 38h			;19ed	ff		.
	rst 38h			;19ee	ff		.
	rst 38h			;19ef	ff		.
	rst 38h			;19f0	ff		.
	rst 38h			;19f1	ff		.
	rst 38h			;19f2	ff		.
	rst 38h			;19f3	ff		.
	rst 38h			;19f4	ff		.
	rst 38h			;19f5	ff		.
	rst 38h			;19f6	ff		.
	rst 38h			;19f7	ff		.
	rst 38h			;19f8	ff		.
	rst 38h			;19f9	ff		.
	rst 38h			;19fa	ff		.
	rst 38h			;19fb	ff		.
	rst 38h			;19fc	ff		.
	rst 38h			;19fd	ff		.
	rst 38h			;19fe	ff		.
	rst 38h			;19ff	ff		.
	rst 38h			;1a00	ff		.
	rst 38h			;1a01	ff		.
	rst 38h			;1a02	ff		.
	rst 38h			;1a03	ff		.
	rst 38h			;1a04	ff		.
	rst 38h			;1a05	ff		.
	rst 38h			;1a06	ff		.
	rst 38h			;1a07	ff		.
	rst 38h			;1a08	ff		.
	rst 38h			;1a09	ff		.
	rst 38h			;1a0a	ff		.
	rst 38h			;1a0b	ff		.
	rst 38h			;1a0c	ff		.
	rst 38h			;1a0d	ff		.
	rst 38h			;1a0e	ff		.
	rst 38h			;1a0f	ff		.
	rst 38h			;1a10	ff		.
	rst 38h			;1a11	ff		.
	rst 38h			;1a12	ff		.
	rst 38h			;1a13	ff		.
	rst 38h			;1a14	ff		.
	rst 38h			;1a15	ff		.
	rst 38h			;1a16	ff		.
	rst 38h			;1a17	ff		.
	rst 38h			;1a18	ff		.
	rst 38h			;1a19	ff		.
	rst 38h			;1a1a	ff		.
	rst 38h			;1a1b	ff		.
	rst 38h			;1a1c	ff		.
	rst 38h			;1a1d	ff		.
	rst 38h			;1a1e	ff		.
	rst 38h			;1a1f	ff		.
	rst 38h			;1a20	ff		.
	rst 38h			;1a21	ff		.
	rst 38h			;1a22	ff		.
	rst 38h			;1a23	ff		.
	rst 38h			;1a24	ff		.
	rst 38h			;1a25	ff		.
	rst 38h			;1a26	ff		.
	rst 38h			;1a27	ff		.
	rst 38h			;1a28	ff		.
	rst 38h			;1a29	ff		.
	rst 38h			;1a2a	ff		.
	rst 38h			;1a2b	ff		.
	rst 38h			;1a2c	ff		.
	rst 38h			;1a2d	ff		.
	rst 38h			;1a2e	ff		.
	rst 38h			;1a2f	ff		.
	rst 38h			;1a30	ff		.
	rst 38h			;1a31	ff		.
	rst 38h			;1a32	ff		.
	rst 38h			;1a33	ff		.
	rst 38h			;1a34	ff		.
	rst 38h			;1a35	ff		.
	rst 38h			;1a36	ff		.
	rst 38h			;1a37	ff		.
	rst 38h			;1a38	ff		.
	rst 38h			;1a39	ff		.
	rst 38h			;1a3a	ff		.
	rst 38h			;1a3b	ff		.
	rst 38h			;1a3c	ff		.
	rst 38h			;1a3d	ff		.
	rst 38h			;1a3e	ff		.
	rst 38h			;1a3f	ff		.
	rst 38h			;1a40	ff		.
	rst 38h			;1a41	ff		.
	rst 38h			;1a42	ff		.
	rst 38h			;1a43	ff		.
	rst 38h			;1a44	ff		.
	rst 38h			;1a45	ff		.
	rst 38h			;1a46	ff		.
	rst 38h			;1a47	ff		.
	rst 38h			;1a48	ff		.
	rst 38h			;1a49	ff		.
	rst 38h			;1a4a	ff		.
	rst 38h			;1a4b	ff		.
	rst 38h			;1a4c	ff		.
	rst 38h			;1a4d	ff		.
	rst 38h			;1a4e	ff		.
	rst 38h			;1a4f	ff		.
	rst 38h			;1a50	ff		.
	rst 38h			;1a51	ff		.
	rst 38h			;1a52	ff		.
	rst 38h			;1a53	ff		.
	rst 38h			;1a54	ff		.
	rst 38h			;1a55	ff		.
	rst 38h			;1a56	ff		.
	rst 38h			;1a57	ff		.
	rst 38h			;1a58	ff		.
	rst 38h			;1a59	ff		.
	rst 38h			;1a5a	ff		.
	rst 38h			;1a5b	ff		.
	rst 38h			;1a5c	ff		.
	rst 38h			;1a5d	ff		.
	rst 38h			;1a5e	ff		.
	rst 38h			;1a5f	ff		.
	rst 38h			;1a60	ff		.
	rst 38h			;1a61	ff		.
	rst 38h			;1a62	ff		.
	rst 38h			;1a63	ff		.
	rst 38h			;1a64	ff		.
	rst 38h			;1a65	ff		.
	rst 38h			;1a66	ff		.
	rst 38h			;1a67	ff		.
	rst 38h			;1a68	ff		.
	rst 38h			;1a69	ff		.
	rst 38h			;1a6a	ff		.
	rst 38h			;1a6b	ff		.
	rst 38h			;1a6c	ff		.
	rst 38h			;1a6d	ff		.
	rst 38h			;1a6e	ff		.
	rst 38h			;1a6f	ff		.
	rst 38h			;1a70	ff		.
	rst 38h			;1a71	ff		.
	rst 38h			;1a72	ff		.
	rst 38h			;1a73	ff		.
	rst 38h			;1a74	ff		.
	rst 38h			;1a75	ff		.
	rst 38h			;1a76	ff		.
	rst 38h			;1a77	ff		.
	rst 38h			;1a78	ff		.
	rst 38h			;1a79	ff		.
	rst 38h			;1a7a	ff		.
	rst 38h			;1a7b	ff		.
	rst 38h			;1a7c	ff		.
	rst 38h			;1a7d	ff		.
	rst 38h			;1a7e	ff		.
	rst 38h			;1a7f	ff		.
	rst 38h			;1a80	ff		.
	rst 38h			;1a81	ff		.
	rst 38h			;1a82	ff		.
	rst 38h			;1a83	ff		.
	rst 38h			;1a84	ff		.
	rst 38h			;1a85	ff		.
	rst 38h			;1a86	ff		.
	rst 38h			;1a87	ff		.
	rst 38h			;1a88	ff		.
	rst 38h			;1a89	ff		.
	rst 38h			;1a8a	ff		.
	rst 38h			;1a8b	ff		.
	rst 38h			;1a8c	ff		.
	rst 38h			;1a8d	ff		.
	rst 38h			;1a8e	ff		.
	rst 38h			;1a8f	ff		.
	rst 38h			;1a90	ff		.
	rst 38h			;1a91	ff		.
	rst 38h			;1a92	ff		.
	rst 38h			;1a93	ff		.
	rst 38h			;1a94	ff		.
	rst 38h			;1a95	ff		.
	rst 38h			;1a96	ff		.
	rst 38h			;1a97	ff		.
	rst 38h			;1a98	ff		.
	rst 38h			;1a99	ff		.
	rst 38h			;1a9a	ff		.
	rst 38h			;1a9b	ff		.
	rst 38h			;1a9c	ff		.
	rst 38h			;1a9d	ff		.
	rst 38h			;1a9e	ff		.
	rst 38h			;1a9f	ff		.
	rst 38h			;1aa0	ff		.
	rst 38h			;1aa1	ff		.
	rst 38h			;1aa2	ff		.
	rst 38h			;1aa3	ff		.
	rst 38h			;1aa4	ff		.
	rst 38h			;1aa5	ff		.
	rst 38h			;1aa6	ff		.
	rst 38h			;1aa7	ff		.
	rst 38h			;1aa8	ff		.
	rst 38h			;1aa9	ff		.
	rst 38h			;1aaa	ff		.
	rst 38h			;1aab	ff		.
	rst 38h			;1aac	ff		.
	rst 38h			;1aad	ff		.
	rst 38h			;1aae	ff		.
	rst 38h			;1aaf	ff		.
	rst 38h			;1ab0	ff		.
	rst 38h			;1ab1	ff		.
	rst 38h			;1ab2	ff		.
	rst 38h			;1ab3	ff		.
	rst 38h			;1ab4	ff		.
	rst 38h			;1ab5	ff		.
	rst 38h			;1ab6	ff		.
	rst 38h			;1ab7	ff		.
	rst 38h			;1ab8	ff		.
	rst 38h			;1ab9	ff		.
	rst 38h			;1aba	ff		.
	rst 38h			;1abb	ff		.
	rst 38h			;1abc	ff		.
	rst 38h			;1abd	ff		.
	rst 38h			;1abe	ff		.
	rst 38h			;1abf	ff		.
	rst 38h			;1ac0	ff		.
	rst 38h			;1ac1	ff		.
	rst 38h			;1ac2	ff		.
	rst 38h			;1ac3	ff		.
	rst 38h			;1ac4	ff		.
	rst 38h			;1ac5	ff		.
	rst 38h			;1ac6	ff		.
	rst 38h			;1ac7	ff		.
	rst 38h			;1ac8	ff		.
	rst 38h			;1ac9	ff		.
	rst 38h			;1aca	ff		.
	rst 38h			;1acb	ff		.
	rst 38h			;1acc	ff		.
	rst 38h			;1acd	ff		.
	rst 38h			;1ace	ff		.
	rst 38h			;1acf	ff		.
	rst 38h			;1ad0	ff		.
	rst 38h			;1ad1	ff		.
	rst 38h			;1ad2	ff		.
	rst 38h			;1ad3	ff		.
	rst 38h			;1ad4	ff		.
	rst 38h			;1ad5	ff		.
	rst 38h			;1ad6	ff		.
	rst 38h			;1ad7	ff		.
	rst 38h			;1ad8	ff		.
	rst 38h			;1ad9	ff		.
	rst 38h			;1ada	ff		.
	rst 38h			;1adb	ff		.
	rst 38h			;1adc	ff		.
	rst 38h			;1add	ff		.
	rst 38h			;1ade	ff		.
	rst 38h			;1adf	ff		.
	rst 38h			;1ae0	ff		.
	rst 38h			;1ae1	ff		.
	rst 38h			;1ae2	ff		.
	rst 38h			;1ae3	ff		.
	rst 38h			;1ae4	ff		.
	rst 38h			;1ae5	ff		.
	rst 38h			;1ae6	ff		.
	rst 38h			;1ae7	ff		.
	rst 38h			;1ae8	ff		.
	rst 38h			;1ae9	ff		.
	rst 38h			;1aea	ff		.
	rst 38h			;1aeb	ff		.
	rst 38h			;1aec	ff		.
	rst 38h			;1aed	ff		.
	rst 38h			;1aee	ff		.
	rst 38h			;1aef	ff		.
	rst 38h			;1af0	ff		.
	rst 38h			;1af1	ff		.
	rst 38h			;1af2	ff		.
	rst 38h			;1af3	ff		.
	rst 38h			;1af4	ff		.
	rst 38h			;1af5	ff		.
	rst 38h			;1af6	ff		.
	rst 38h			;1af7	ff		.
	rst 38h			;1af8	ff		.
	rst 38h			;1af9	ff		.
	rst 38h			;1afa	ff		.
	rst 38h			;1afb	ff		.
	rst 38h			;1afc	ff		.
	rst 38h			;1afd	ff		.
	rst 38h			;1afe	ff		.
	rst 38h			;1aff	ff		.
	rst 38h			;1b00	ff		.
	rst 38h			;1b01	ff		.
	rst 38h			;1b02	ff		.
	rst 38h			;1b03	ff		.
	rst 38h			;1b04	ff		.
	rst 38h			;1b05	ff		.
	rst 38h			;1b06	ff		.
	rst 38h			;1b07	ff		.
	rst 38h			;1b08	ff		.
	rst 38h			;1b09	ff		.
	rst 38h			;1b0a	ff		.
	rst 38h			;1b0b	ff		.
	rst 38h			;1b0c	ff		.
	rst 38h			;1b0d	ff		.
	rst 38h			;1b0e	ff		.
	rst 38h			;1b0f	ff		.
	rst 38h			;1b10	ff		.
	rst 38h			;1b11	ff		.
	rst 38h			;1b12	ff		.
	rst 38h			;1b13	ff		.
	rst 38h			;1b14	ff		.
	rst 38h			;1b15	ff		.
	rst 38h			;1b16	ff		.
	rst 38h			;1b17	ff		.
	rst 38h			;1b18	ff		.
	rst 38h			;1b19	ff		.
	rst 38h			;1b1a	ff		.
	rst 38h			;1b1b	ff		.
	rst 38h			;1b1c	ff		.
	rst 38h			;1b1d	ff		.
	rst 38h			;1b1e	ff		.
	rst 38h			;1b1f	ff		.
	rst 38h			;1b20	ff		.
	rst 38h			;1b21	ff		.
	rst 38h			;1b22	ff		.
	rst 38h			;1b23	ff		.
	rst 38h			;1b24	ff		.
	rst 38h			;1b25	ff		.
	rst 38h			;1b26	ff		.
	rst 38h			;1b27	ff		.
	rst 38h			;1b28	ff		.
	rst 38h			;1b29	ff		.
	rst 38h			;1b2a	ff		.
	rst 38h			;1b2b	ff		.
	rst 38h			;1b2c	ff		.
	rst 38h			;1b2d	ff		.
	rst 38h			;1b2e	ff		.
	rst 38h			;1b2f	ff		.
	rst 38h			;1b30	ff		.
	rst 38h			;1b31	ff		.
	rst 38h			;1b32	ff		.
	rst 38h			;1b33	ff		.
	rst 38h			;1b34	ff		.
	rst 38h			;1b35	ff		.
	rst 38h			;1b36	ff		.
	rst 38h			;1b37	ff		.
	rst 38h			;1b38	ff		.
	rst 38h			;1b39	ff		.
	rst 38h			;1b3a	ff		.
	rst 38h			;1b3b	ff		.
	rst 38h			;1b3c	ff		.
	rst 38h			;1b3d	ff		.
	rst 38h			;1b3e	ff		.
	rst 38h			;1b3f	ff		.
	rst 38h			;1b40	ff		.
	rst 38h			;1b41	ff		.
	rst 38h			;1b42	ff		.
	rst 38h			;1b43	ff		.
	rst 38h			;1b44	ff		.
	rst 38h			;1b45	ff		.
	rst 38h			;1b46	ff		.
	rst 38h			;1b47	ff		.
	rst 38h			;1b48	ff		.
	rst 38h			;1b49	ff		.
	rst 38h			;1b4a	ff		.
	rst 38h			;1b4b	ff		.
	rst 38h			;1b4c	ff		.
	rst 38h			;1b4d	ff		.
	rst 38h			;1b4e	ff		.
	rst 38h			;1b4f	ff		.
	rst 38h			;1b50	ff		.
	rst 38h			;1b51	ff		.
	rst 38h			;1b52	ff		.
	rst 38h			;1b53	ff		.
	rst 38h			;1b54	ff		.
	rst 38h			;1b55	ff		.
	rst 38h			;1b56	ff		.
	rst 38h			;1b57	ff		.
	rst 38h			;1b58	ff		.
	rst 38h			;1b59	ff		.
	rst 38h			;1b5a	ff		.
	rst 38h			;1b5b	ff		.
	rst 38h			;1b5c	ff		.
	rst 38h			;1b5d	ff		.
	rst 38h			;1b5e	ff		.
	rst 38h			;1b5f	ff		.
	rst 38h			;1b60	ff		.
	rst 38h			;1b61	ff		.
	rst 38h			;1b62	ff		.
	rst 38h			;1b63	ff		.
	rst 38h			;1b64	ff		.
	rst 38h			;1b65	ff		.
	rst 38h			;1b66	ff		.
	rst 38h			;1b67	ff		.
	rst 38h			;1b68	ff		.
	rst 38h			;1b69	ff		.
	rst 38h			;1b6a	ff		.
	rst 38h			;1b6b	ff		.
	rst 38h			;1b6c	ff		.
	rst 38h			;1b6d	ff		.
	rst 38h			;1b6e	ff		.
	rst 38h			;1b6f	ff		.
	rst 38h			;1b70	ff		.
	rst 38h			;1b71	ff		.
	rst 38h			;1b72	ff		.
	rst 38h			;1b73	ff		.
	rst 38h			;1b74	ff		.
	rst 38h			;1b75	ff		.
	rst 38h			;1b76	ff		.
	rst 38h			;1b77	ff		.
	rst 38h			;1b78	ff		.
	rst 38h			;1b79	ff		.
	rst 38h			;1b7a	ff		.
	rst 38h			;1b7b	ff		.
	rst 38h			;1b7c	ff		.
	rst 38h			;1b7d	ff		.
	rst 38h			;1b7e	ff		.
	rst 38h			;1b7f	ff		.
	rst 38h			;1b80	ff		.
	rst 38h			;1b81	ff		.
	rst 38h			;1b82	ff		.
	rst 38h			;1b83	ff		.
	rst 38h			;1b84	ff		.
	rst 38h			;1b85	ff		.
	rst 38h			;1b86	ff		.
	rst 38h			;1b87	ff		.
	rst 38h			;1b88	ff		.
	rst 38h			;1b89	ff		.
	rst 38h			;1b8a	ff		.
	rst 38h			;1b8b	ff		.
	rst 38h			;1b8c	ff		.
	rst 38h			;1b8d	ff		.
	rst 38h			;1b8e	ff		.
	rst 38h			;1b8f	ff		.
	rst 38h			;1b90	ff		.
	rst 38h			;1b91	ff		.
	rst 38h			;1b92	ff		.
	rst 38h			;1b93	ff		.
	rst 38h			;1b94	ff		.
	rst 38h			;1b95	ff		.
	rst 38h			;1b96	ff		.
	rst 38h			;1b97	ff		.
	rst 38h			;1b98	ff		.
	rst 38h			;1b99	ff		.
	rst 38h			;1b9a	ff		.
	rst 38h			;1b9b	ff		.
	rst 38h			;1b9c	ff		.
	rst 38h			;1b9d	ff		.
	rst 38h			;1b9e	ff		.
	rst 38h			;1b9f	ff		.
	rst 38h			;1ba0	ff		.
	rst 38h			;1ba1	ff		.
	rst 38h			;1ba2	ff		.
	rst 38h			;1ba3	ff		.
	rst 38h			;1ba4	ff		.
	rst 38h			;1ba5	ff		.
	rst 38h			;1ba6	ff		.
	rst 38h			;1ba7	ff		.
	rst 38h			;1ba8	ff		.
	rst 38h			;1ba9	ff		.
	rst 38h			;1baa	ff		.
	rst 38h			;1bab	ff		.
	rst 38h			;1bac	ff		.
	rst 38h			;1bad	ff		.
	rst 38h			;1bae	ff		.
	rst 38h			;1baf	ff		.
	rst 38h			;1bb0	ff		.
	rst 38h			;1bb1	ff		.
	rst 38h			;1bb2	ff		.
	rst 38h			;1bb3	ff		.
	rst 38h			;1bb4	ff		.
	rst 38h			;1bb5	ff		.
	rst 38h			;1bb6	ff		.
	rst 38h			;1bb7	ff		.
	rst 38h			;1bb8	ff		.
	rst 38h			;1bb9	ff		.
	rst 38h			;1bba	ff		.
	rst 38h			;1bbb	ff		.
	rst 38h			;1bbc	ff		.
	rst 38h			;1bbd	ff		.
	rst 38h			;1bbe	ff		.
	rst 38h			;1bbf	ff		.
	rst 38h			;1bc0	ff		.
	rst 38h			;1bc1	ff		.
	rst 38h			;1bc2	ff		.
	rst 38h			;1bc3	ff		.
	rst 38h			;1bc4	ff		.
	rst 38h			;1bc5	ff		.
	rst 38h			;1bc6	ff		.
	rst 38h			;1bc7	ff		.
	rst 38h			;1bc8	ff		.
	rst 38h			;1bc9	ff		.
	rst 38h			;1bca	ff		.
	rst 38h			;1bcb	ff		.
	rst 38h			;1bcc	ff		.
	rst 38h			;1bcd	ff		.
	rst 38h			;1bce	ff		.
	rst 38h			;1bcf	ff		.
	rst 38h			;1bd0	ff		.
	rst 38h			;1bd1	ff		.
	rst 38h			;1bd2	ff		.
	rst 38h			;1bd3	ff		.
	rst 38h			;1bd4	ff		.
	rst 38h			;1bd5	ff		.
	rst 38h			;1bd6	ff		.
	rst 38h			;1bd7	ff		.
	rst 38h			;1bd8	ff		.
	rst 38h			;1bd9	ff		.
	rst 38h			;1bda	ff		.
	rst 38h			;1bdb	ff		.
	rst 38h			;1bdc	ff		.
	rst 38h			;1bdd	ff		.
	rst 38h			;1bde	ff		.
	rst 38h			;1bdf	ff		.
	rst 38h			;1be0	ff		.
	rst 38h			;1be1	ff		.
	rst 38h			;1be2	ff		.
	rst 38h			;1be3	ff		.
	rst 38h			;1be4	ff		.
l1be5h:
	rst 38h			;1be5	ff		.
	rst 38h			;1be6	ff		.
	rst 38h			;1be7	ff		.
	rst 38h			;1be8	ff		.
	rst 38h			;1be9	ff		.
	rst 38h			;1bea	ff		.
	rst 38h			;1beb	ff		.
	rst 38h			;1bec	ff		.
l1bedh:
	rst 38h			;1bed	ff		.
	rst 38h			;1bee	ff		.
l1befh:
	rst 38h			;1bef	ff		.
	rst 38h			;1bf0	ff		.
	rst 38h			;1bf1	ff		.
	rst 38h			;1bf2	ff		.
	rst 38h			;1bf3	ff		.
	rst 38h			;1bf4	ff		.
	rst 38h			;1bf5	ff		.
	rst 38h			;1bf6	ff		.
	rst 38h			;1bf7	ff		.
	rst 38h			;1bf8	ff		.
	rst 38h			;1bf9	ff		.
	rst 38h			;1bfa	ff		.
	rst 38h			;1bfb	ff		.
	rst 38h			;1bfc	ff		.
	rst 38h			;1bfd	ff		.
	rst 38h			;1bfe	ff		.
	rst 38h			;1bff	ff		.
	nop			;1c00	00		.
	nop			;1c01	00		.
	nop			;1c02	00		.
	nop			;1c03	00		.
	nop			;1c04	00		.
	nop			;1c05	00		.
	nop			;1c06	00		.
	nop			;1c07	00		.
	nop			;1c08	00		.
	nop			;1c09	00		.
	nop			;1c0a	00		.
	nop			;1c0b	00		.
	nop			;1c0c	00		.
	nop			;1c0d	00		.
	nop			;1c0e	00		.
	nop			;1c0f	00		.
	nop			;1c10	00		.
	nop			;1c11	00		.
	nop			;1c12	00		.
	nop			;1c13	00		.
	nop			;1c14	00		.
	nop			;1c15	00		.
	nop			;1c16	00		.
	nop			;1c17	00		.
	nop			;1c18	00		.
	nop			;1c19	00		.
	nop			;1c1a	00		.
	nop			;1c1b	00		.
	nop			;1c1c	00		.
	nop			;1c1d	00		.
	nop			;1c1e	00		.
	nop			;1c1f	00		.
	nop			;1c20	00		.
	nop			;1c21	00		.
	nop			;1c22	00		.
	nop			;1c23	00		.
	nop			;1c24	00		.
	nop			;1c25	00		.
	nop			;1c26	00		.
	nop			;1c27	00		.
	nop			;1c28	00		.
	nop			;1c29	00		.
	nop			;1c2a	00		.
	nop			;1c2b	00		.
	nop			;1c2c	00		.
	nop			;1c2d	00		.
	nop			;1c2e	00		.
	nop			;1c2f	00		.
	nop			;1c30	00		.
	nop			;1c31	00		.
	nop			;1c32	00		.
	nop			;1c33	00		.
	nop			;1c34	00		.
	nop			;1c35	00		.
	nop			;1c36	00		.
	nop			;1c37	00		.
	nop			;1c38	00		.
	nop			;1c39	00		.
	nop			;1c3a	00		.
	nop			;1c3b	00		.
	nop			;1c3c	00		.
	nop			;1c3d	00		.
	nop			;1c3e	00		.
	nop			;1c3f	00		.
	nop			;1c40	00		.
	nop			;1c41	00		.
	nop			;1c42	00		.
	nop			;1c43	00		.
	nop			;1c44	00		.
	nop			;1c45	00		.
	nop			;1c46	00		.
	nop			;1c47	00		.
	nop			;1c48	00		.
	nop			;1c49	00		.
	nop			;1c4a	00		.
	nop			;1c4b	00		.
	nop			;1c4c	00		.
	nop			;1c4d	00		.
	nop			;1c4e	00		.
	nop			;1c4f	00		.
	nop			;1c50	00		.
l1c51h:
	nop			;1c51	00		.
	nop			;1c52	00		.
	nop			;1c53	00		.
	nop			;1c54	00		.
	nop			;1c55	00		.
	nop			;1c56	00		.
	nop			;1c57	00		.
	nop			;1c58	00		.
	nop			;1c59	00		.
	nop			;1c5a	00		.
	nop			;1c5b	00		.
	nop			;1c5c	00		.
	nop			;1c5d	00		.
	nop			;1c5e	00		.
	nop			;1c5f	00		.
	nop			;1c60	00		.
	nop			;1c61	00		.
	nop			;1c62	00		.
	nop			;1c63	00		.
	nop			;1c64	00		.
	nop			;1c65	00		.
	nop			;1c66	00		.
	nop			;1c67	00		.
	nop			;1c68	00		.
	nop			;1c69	00		.
	nop			;1c6a	00		.
	nop			;1c6b	00		.
	nop			;1c6c	00		.
	nop			;1c6d	00		.
	nop			;1c6e	00		.
	nop			;1c6f	00		.
	nop			;1c70	00		.
	nop			;1c71	00		.
	nop			;1c72	00		.
	nop			;1c73	00		.
	nop			;1c74	00		.
	nop			;1c75	00		.
	nop			;1c76	00		.
	nop			;1c77	00		.
	nop			;1c78	00		.
	nop			;1c79	00		.
	nop			;1c7a	00		.
	nop			;1c7b	00		.
	nop			;1c7c	00		.
	nop			;1c7d	00		.
	nop			;1c7e	00		.
	nop			;1c7f	00		.
	nop			;1c80	00		.
	nop			;1c81	00		.
	nop			;1c82	00		.
	nop			;1c83	00		.
	nop			;1c84	00		.
	nop			;1c85	00		.
	nop			;1c86	00		.
	nop			;1c87	00		.
	nop			;1c88	00		.
	nop			;1c89	00		.
	nop			;1c8a	00		.
	nop			;1c8b	00		.
	nop			;1c8c	00		.
	nop			;1c8d	00		.
	nop			;1c8e	00		.
	nop			;1c8f	00		.
	nop			;1c90	00		.
	nop			;1c91	00		.
	nop			;1c92	00		.
	nop			;1c93	00		.
	nop			;1c94	00		.
	nop			;1c95	00		.
	nop			;1c96	00		.
	nop			;1c97	00		.
	nop			;1c98	00		.
	nop			;1c99	00		.
	nop			;1c9a	00		.
	nop			;1c9b	00		.
	nop			;1c9c	00		.
	nop			;1c9d	00		.
	nop			;1c9e	00		.
	nop			;1c9f	00		.
	nop			;1ca0	00		.
	nop			;1ca1	00		.
	nop			;1ca2	00		.
	nop			;1ca3	00		.
	nop			;1ca4	00		.
	nop			;1ca5	00		.
	nop			;1ca6	00		.
	nop			;1ca7	00		.
	nop			;1ca8	00		.
	nop			;1ca9	00		.
	nop			;1caa	00		.
	nop			;1cab	00		.
	nop			;1cac	00		.
	nop			;1cad	00		.
	nop			;1cae	00		.
	nop			;1caf	00		.
	nop			;1cb0	00		.
	nop			;1cb1	00		.
	nop			;1cb2	00		.
	nop			;1cb3	00		.
	nop			;1cb4	00		.
	nop			;1cb5	00		.
	nop			;1cb6	00		.
	nop			;1cb7	00		.
	nop			;1cb8	00		.
	nop			;1cb9	00		.
	nop			;1cba	00		.
	nop			;1cbb	00		.
	nop			;1cbc	00		.
	nop			;1cbd	00		.
	nop			;1cbe	00		.
	nop			;1cbf	00		.
	nop			;1cc0	00		.
	nop			;1cc1	00		.
	nop			;1cc2	00		.
	nop			;1cc3	00		.
	nop			;1cc4	00		.
	nop			;1cc5	00		.
	nop			;1cc6	00		.
	nop			;1cc7	00		.
	nop			;1cc8	00		.
	nop			;1cc9	00		.
	nop			;1cca	00		.
	nop			;1ccb	00		.
	nop			;1ccc	00		.
	nop			;1ccd	00		.
	nop			;1cce	00		.
	nop			;1ccf	00		.
	nop			;1cd0	00		.
	nop			;1cd1	00		.
	nop			;1cd2	00		.
	nop			;1cd3	00		.
	nop			;1cd4	00		.
	nop			;1cd5	00		.
	nop			;1cd6	00		.
	nop			;1cd7	00		.
	nop			;1cd8	00		.
	nop			;1cd9	00		.
	nop			;1cda	00		.
	nop			;1cdb	00		.
	nop			;1cdc	00		.
	nop			;1cdd	00		.
	nop			;1cde	00		.
	nop			;1cdf	00		.
	nop			;1ce0	00		.
	nop			;1ce1	00		.
	nop			;1ce2	00		.
	nop			;1ce3	00		.
	nop			;1ce4	00		.
	nop			;1ce5	00		.
	nop			;1ce6	00		.
	nop			;1ce7	00		.
	nop			;1ce8	00		.
	nop			;1ce9	00		.
	nop			;1cea	00		.
	nop			;1ceb	00		.
	nop			;1cec	00		.
	nop			;1ced	00		.
	nop			;1cee	00		.
	nop			;1cef	00		.
	nop			;1cf0	00		.
	nop			;1cf1	00		.
	nop			;1cf2	00		.
	nop			;1cf3	00		.
	nop			;1cf4	00		.
	nop			;1cf5	00		.
	nop			;1cf6	00		.
	nop			;1cf7	00		.
	nop			;1cf8	00		.
	nop			;1cf9	00		.
	nop			;1cfa	00		.
	nop			;1cfb	00		.
	nop			;1cfc	00		.
	nop			;1cfd	00		.
	nop			;1cfe	00		.
	nop			;1cff	00		.
l1d00h:
	ld (04d62h),a		;1d00	32 62 4d	2 b M
	ld h,d			;1d03	62		b
	ld (hl),d		;1d04	72		r
	ld h,d			;1d05	62		b
	xor e			;1d06	ab		.
	ld h,d			;1d07	62		b
	cp b			;1d08	b8		.
	ld h,d			;1d09	62		b
	call 0d362h		;1d0a	cd 62 d3	. b .
	ld h,d			;1d0d	62		b
	call c,0fb62h		;1d0e	dc 62 fb	. b .
	ld h,d			;1d11	62		b
	ld a,(de)		;1d12	1a		.
	ld h,e			;1d13	63		c
	jr nz,$+101		;1d14	20 63		  c
	inc h			;1d16	24		$
	ld h,e			;1d17	63		c
	ld hl,(03563h)		;1d18	2a 63 35	* c 5
	ld h,e			;1d1b	63		c
	ld a,063h		;1d1c	3e 63		> c
	ld b,h			;1d1e	44		D
	ld h,e			;1d1f	63		c
	ld c,b			;1d20	48		H
	ld h,e			;1d21	63		c
	ld c,(hl)		;1d22	4e		N
	ld h,e			;1d23	63		c
	ld d,a			;1d24	57		W
	ld h,e			;1d25	63		c
	rla			;1d26	17		.
	ld h,h			;1d27	64		d
	ld e,064h		;1d28	1e 64		. d
	jr z,l1d90h		;1d2a	28 64		( d
	ld h,c			;1d2c	61		a
	ld h,h			;1d2d	64		d
	ld h,l			;1d2e	65		e
	ld h,h			;1d2f	64		d
	ld l,l			;1d30	6d		m
	ld h,h			;1d31	64		d
	sbc a,a			;1d32	9f		.
	ld h,h			;1d33	64		d
	xor h			;1d34	ac		.
	ld h,h			;1d35	64		d
	or e			;1d36	b3		.
	ld h,h			;1d37	64		d
	ld c,065h		;1d38	0e 65		. e
	ld d,065h		;1d3a	16 65		. e
	ld (03a65h),a		;1d3c	32 65 3a	2 e :
	ld h,l			;1d3f	65		e
	ld e,h			;1d40	5c		\
	ld h,l			;1d41	65		e
	ld h,(hl)		;1d42	66		f
	ld h,l			;1d43	65		e
	adc a,065h		;1d44	ce 65		. e
	add a,l			;1d46	85		.
	ld h,l			;1d47	65		e
	out (065h),a		;1d48	d3 65		. e
	defb 0edh ;next byte illegal after ed	;1d4a	ed		.
	ld h,l			;1d4b	65		e
	ld sp,hl		;1d4c	f9		.
	ld h,l			;1d4d	65		e
	ld e,066h		;1d4e	1e 66		. f
	dec l			;1d50	2d		-
	ld h,(hl)		;1d51	66		f
	ld a,(04266h)		;1d52	3a 66 42	: f B
	ld h,(hl)		;1d55	66		f
	ld d,b			;1d56	50		P
	ld h,(hl)		;1d57	66		f
	ld h,(hl)		;1d58	66		f
	ld h,(hl)		;1d59	66		f
	ld (hl),d		;1d5a	72		r
	ld h,(hl)		;1d5b	66		f
	add a,b			;1d5c	80		.
	ld h,(hl)		;1d5d	66		f
	sub h			;1d5e	94		.
	ld h,(hl)		;1d5f	66		f
	ret nz			;1d60	c0		.
	ld h,(hl)		;1d61	66		f
	ld h,(iy+003h)		;1d62	fd 66 03	. f .
	ld h,a			;1d65	67		g
	jr nc,l1dcfh		;1d66	30 67		0 g
	ld c,a			;1d68	4f		O
	ld h,a			;1d69	67		g
	ld d,b			;1d6a	50		P
	ld h,a			;1d6b	67		g
	ld e,d			;1d6c	5a		Z
	ld h,a			;1d6d	67		g
	halt			;1d6e	76		v
	ld h,a			;1d6f	67		g
	ld a,l			;1d70	7d		}
	ld h,a			;1d71	67		g
	and a			;1d72	a7		.
	ld h,a			;1d73	67		g
	call c,0e367h		;1d74	dc 67 e3	. g .
	ld h,a			;1d77	67		g
	or 067h			;1d78	f6 67		. g
	nop			;1d7a	00		.
	nop			;1d7b	00		.
	nop			;1d7c	00		.
	nop			;1d7d	00		.
	nop			;1d7e	00		.
	nop			;1d7f	00		.
	nop			;1d80	00		.
	nop			;1d81	00		.
	nop			;1d82	00		.
	nop			;1d83	00		.
	nop			;1d84	00		.
	nop			;1d85	00		.
	nop			;1d86	00		.
	nop			;1d87	00		.
	nop			;1d88	00		.
	nop			;1d89	00		.
	nop			;1d8a	00		.
	nop			;1d8b	00		.
	nop			;1d8c	00		.
	nop			;1d8d	00		.
	nop			;1d8e	00		.
	nop			;1d8f	00		.
l1d90h:
	nop			;1d90	00		.
	nop			;1d91	00		.
	nop			;1d92	00		.
	nop			;1d93	00		.
	nop			;1d94	00		.
	nop			;1d95	00		.
	nop			;1d96	00		.
	nop			;1d97	00		.
	nop			;1d98	00		.
	nop			;1d99	00		.
	nop			;1d9a	00		.
	nop			;1d9b	00		.
	nop			;1d9c	00		.
	nop			;1d9d	00		.
	nop			;1d9e	00		.
	nop			;1d9f	00		.
	nop			;1da0	00		.
	nop			;1da1	00		.
	nop			;1da2	00		.
	nop			;1da3	00		.
	nop			;1da4	00		.
	nop			;1da5	00		.
	nop			;1da6	00		.
	nop			;1da7	00		.
	nop			;1da8	00		.
	nop			;1da9	00		.
	nop			;1daa	00		.
	nop			;1dab	00		.
	nop			;1dac	00		.
	nop			;1dad	00		.
	nop			;1dae	00		.
	nop			;1daf	00		.
	nop			;1db0	00		.
	nop			;1db1	00		.
	nop			;1db2	00		.
	nop			;1db3	00		.
	nop			;1db4	00		.
	nop			;1db5	00		.
	nop			;1db6	00		.
	nop			;1db7	00		.
	nop			;1db8	00		.
	nop			;1db9	00		.
	nop			;1dba	00		.
	nop			;1dbb	00		.
	nop			;1dbc	00		.
	nop			;1dbd	00		.
	nop			;1dbe	00		.
	nop			;1dbf	00		.
	nop			;1dc0	00		.
	nop			;1dc1	00		.
	nop			;1dc2	00		.
	nop			;1dc3	00		.
	nop			;1dc4	00		.
	nop			;1dc5	00		.
	nop			;1dc6	00		.
	nop			;1dc7	00		.
	nop			;1dc8	00		.
	nop			;1dc9	00		.
	nop			;1dca	00		.
	nop			;1dcb	00		.
	nop			;1dcc	00		.
	nop			;1dcd	00		.
	nop			;1dce	00		.
l1dcfh:
	nop			;1dcf	00		.
	nop			;1dd0	00		.
	nop			;1dd1	00		.
	nop			;1dd2	00		.
	nop			;1dd3	00		.
	nop			;1dd4	00		.
	nop			;1dd5	00		.
	nop			;1dd6	00		.
	nop			;1dd7	00		.
	nop			;1dd8	00		.
	nop			;1dd9	00		.
	nop			;1dda	00		.
	nop			;1ddb	00		.
	nop			;1ddc	00		.
	nop			;1ddd	00		.
	nop			;1dde	00		.
	nop			;1ddf	00		.
	nop			;1de0	00		.
	nop			;1de1	00		.
	nop			;1de2	00		.
	nop			;1de3	00		.
	nop			;1de4	00		.
	nop			;1de5	00		.
	nop			;1de6	00		.
	nop			;1de7	00		.
	nop			;1de8	00		.
	nop			;1de9	00		.
	nop			;1dea	00		.
	nop			;1deb	00		.
	nop			;1dec	00		.
	nop			;1ded	00		.
	nop			;1dee	00		.
	nop			;1def	00		.
	nop			;1df0	00		.
	nop			;1df1	00		.
	nop			;1df2	00		.
	nop			;1df3	00		.
	nop			;1df4	00		.
	nop			;1df5	00		.
	nop			;1df6	00		.
	nop			;1df7	00		.
	nop			;1df8	00		.
	nop			;1df9	00		.
	nop			;1dfa	00		.
	nop			;1dfb	00		.
	nop			;1dfc	00		.
	nop			;1dfd	00		.
	nop			;1dfe	00		.
	nop			;1dff	00		.
	nop			;1e00	00		.
	nop			;1e01	00		.
	nop			;1e02	00		.
	nop			;1e03	00		.
	nop			;1e04	00		.
	nop			;1e05	00		.
	nop			;1e06	00		.
	nop			;1e07	00		.
	nop			;1e08	00		.
	nop			;1e09	00		.
	nop			;1e0a	00		.
	nop			;1e0b	00		.
	nop			;1e0c	00		.
	nop			;1e0d	00		.
	nop			;1e0e	00		.
	nop			;1e0f	00		.
	nop			;1e10	00		.
	nop			;1e11	00		.
	nop			;1e12	00		.
	nop			;1e13	00		.
	nop			;1e14	00		.
	nop			;1e15	00		.
	nop			;1e16	00		.
	nop			;1e17	00		.
	nop			;1e18	00		.
	nop			;1e19	00		.
	nop			;1e1a	00		.
	nop			;1e1b	00		.
	nop			;1e1c	00		.
	nop			;1e1d	00		.
	nop			;1e1e	00		.
	nop			;1e1f	00		.
	nop			;1e20	00		.
	nop			;1e21	00		.
	nop			;1e22	00		.
	nop			;1e23	00		.
	nop			;1e24	00		.
	nop			;1e25	00		.
	nop			;1e26	00		.
	nop			;1e27	00		.
	nop			;1e28	00		.
	nop			;1e29	00		.
	nop			;1e2a	00		.
	nop			;1e2b	00		.
	nop			;1e2c	00		.
	nop			;1e2d	00		.
	nop			;1e2e	00		.
	nop			;1e2f	00		.
	nop			;1e30	00		.
	nop			;1e31	00		.
	nop			;1e32	00		.
	nop			;1e33	00		.
	nop			;1e34	00		.
	nop			;1e35	00		.
	nop			;1e36	00		.
	nop			;1e37	00		.
	nop			;1e38	00		.
	nop			;1e39	00		.
	nop			;1e3a	00		.
	nop			;1e3b	00		.
	nop			;1e3c	00		.
	nop			;1e3d	00		.
	nop			;1e3e	00		.
	nop			;1e3f	00		.
	nop			;1e40	00		.
	nop			;1e41	00		.
	nop			;1e42	00		.
	nop			;1e43	00		.
	nop			;1e44	00		.
	nop			;1e45	00		.
	nop			;1e46	00		.
	nop			;1e47	00		.
	nop			;1e48	00		.
	nop			;1e49	00		.
	nop			;1e4a	00		.
	nop			;1e4b	00		.
	nop			;1e4c	00		.
	nop			;1e4d	00		.
	nop			;1e4e	00		.
	nop			;1e4f	00		.
	nop			;1e50	00		.
	nop			;1e51	00		.
	nop			;1e52	00		.
	nop			;1e53	00		.
	nop			;1e54	00		.
	nop			;1e55	00		.
	nop			;1e56	00		.
	nop			;1e57	00		.
	nop			;1e58	00		.
	nop			;1e59	00		.
	nop			;1e5a	00		.
	nop			;1e5b	00		.
	nop			;1e5c	00		.
	nop			;1e5d	00		.
	nop			;1e5e	00		.
	nop			;1e5f	00		.
	nop			;1e60	00		.
	nop			;1e61	00		.
	nop			;1e62	00		.
	nop			;1e63	00		.
	nop			;1e64	00		.
	nop			;1e65	00		.
	nop			;1e66	00		.
	nop			;1e67	00		.
	nop			;1e68	00		.
	nop			;1e69	00		.
	nop			;1e6a	00		.
	nop			;1e6b	00		.
	nop			;1e6c	00		.
	nop			;1e6d	00		.
	nop			;1e6e	00		.
	nop			;1e6f	00		.
	nop			;1e70	00		.
	nop			;1e71	00		.
	nop			;1e72	00		.
	nop			;1e73	00		.
	nop			;1e74	00		.
	nop			;1e75	00		.
	nop			;1e76	00		.
	nop			;1e77	00		.
	nop			;1e78	00		.
	nop			;1e79	00		.
	nop			;1e7a	00		.
	nop			;1e7b	00		.
	nop			;1e7c	00		.
	nop			;1e7d	00		.
	nop			;1e7e	00		.
	nop			;1e7f	00		.
	nop			;1e80	00		.
	nop			;1e81	00		.
	nop			;1e82	00		.
	nop			;1e83	00		.
	nop			;1e84	00		.
	nop			;1e85	00		.
	nop			;1e86	00		.
	nop			;1e87	00		.
	nop			;1e88	00		.
	nop			;1e89	00		.
	nop			;1e8a	00		.
	nop			;1e8b	00		.
	nop			;1e8c	00		.
	nop			;1e8d	00		.
	nop			;1e8e	00		.
	nop			;1e8f	00		.
	nop			;1e90	00		.
	nop			;1e91	00		.
	nop			;1e92	00		.
	nop			;1e93	00		.
	nop			;1e94	00		.
	nop			;1e95	00		.
	nop			;1e96	00		.
	nop			;1e97	00		.
	nop			;1e98	00		.
	nop			;1e99	00		.
	nop			;1e9a	00		.
	nop			;1e9b	00		.
	nop			;1e9c	00		.
	nop			;1e9d	00		.
	nop			;1e9e	00		.
	nop			;1e9f	00		.
	nop			;1ea0	00		.
	nop			;1ea1	00		.
	nop			;1ea2	00		.
	nop			;1ea3	00		.
	nop			;1ea4	00		.
	nop			;1ea5	00		.
	nop			;1ea6	00		.
	nop			;1ea7	00		.
	nop			;1ea8	00		.
	nop			;1ea9	00		.
	nop			;1eaa	00		.
	nop			;1eab	00		.
	nop			;1eac	00		.
	nop			;1ead	00		.
	nop			;1eae	00		.
	nop			;1eaf	00		.
	nop			;1eb0	00		.
	nop			;1eb1	00		.
	nop			;1eb2	00		.
	nop			;1eb3	00		.
	nop			;1eb4	00		.
	nop			;1eb5	00		.
	nop			;1eb6	00		.
	nop			;1eb7	00		.
	nop			;1eb8	00		.
	nop			;1eb9	00		.
	nop			;1eba	00		.
	nop			;1ebb	00		.
	nop			;1ebc	00		.
	nop			;1ebd	00		.
	nop			;1ebe	00		.
	nop			;1ebf	00		.
	nop			;1ec0	00		.
	nop			;1ec1	00		.
	nop			;1ec2	00		.
	nop			;1ec3	00		.
	nop			;1ec4	00		.
	nop			;1ec5	00		.
	nop			;1ec6	00		.
	nop			;1ec7	00		.
	nop			;1ec8	00		.
	nop			;1ec9	00		.
	nop			;1eca	00		.
	nop			;1ecb	00		.
	nop			;1ecc	00		.
	nop			;1ecd	00		.
	nop			;1ece	00		.
l1ecfh:
	nop			;1ecf	00		.
	nop			;1ed0	00		.
	nop			;1ed1	00		.
	nop			;1ed2	00		.
	nop			;1ed3	00		.
	nop			;1ed4	00		.
	nop			;1ed5	00		.
	nop			;1ed6	00		.
	nop			;1ed7	00		.
	nop			;1ed8	00		.
	nop			;1ed9	00		.
	nop			;1eda	00		.
	nop			;1edb	00		.
	sub l			;1edc	95		.
	rla			;1edd	17		.
	inc de			;1ede	13		.
	jr z,l1f05h		;1edf	28 24		( $
	ld h,039h		;1ee1	26 39		& 9
	add hl,bc		;1ee3	09		.
	and (hl)		;1ee4	a6		.
	ex af,af'		;1ee5	08		.
	ccf			;1ee6	3f		?
	rlca			;1ee7	07		.
	ld h,(hl)		;1ee8	66		f
	dec b			;1ee9	05		.
	ld d,h			;1eea	54		T
	dec b			;1eeb	05		.
	ld a,(0b005h)		;1eec	3a 05 b0	: . .
	ld (bc),a		;1eef	02		.
	djnz l1ef2h		;1ef0	10 00		. .
l1ef2h:
	defb 0edh ;next byte illegal after ed	;1ef2	ed		.
	ld de,011cfh		;1ef3	11 cf 11	. . .
	ld l,h			;1ef6	6c		l
	inc a			;1ef7	3c		<
	ld h,l			;1ef8	65		e
	inc a			;1ef9	3c		<
	ld e,(hl)		;1efa	5e		^
	inc a			;1efb	3c		<
	ld c,(hl)		;1efc	4e		N
	inc a			;1efd	3c		<
	defb 0fdh,03bh,0f5h ;illegal sequence	;1efe	fd 3b f5	. ; .
	dec sp			;1f01	3b		;
	ret nc			;1f02	d0		.
	dec sp			;1f03	3b		;
	push bc			;1f04	c5		.
l1f05h:
	dec sp			;1f05	3b		;
	sbc a,(hl)		;1f06	9e		.
	dec sp			;1f07	3b		;
	ld l,03bh		;1f08	2e 3b		. ;
	rst 18h			;1f0a	df		.
	ld a,(03acah)		;1f0b	3a ca 3a	: . :
	cp e			;1f0e	bb		.
l1f0fh:
	ld a,(03656h)		;1f0f	3a 56 36	: V 6
	out (035h),a		;1f12	d3 35		. 5
	ld l,(hl)		;1f14	6e		n
	dec (hl)		;1f15	35		5
	adc a,c			;1f16	89		.
	inc (hl)		;1f17	34		4
	ld l,b			;1f18	68		h
	inc (hl)		;1f19	34		4
	out (033h),a		;1f1a	d3 33		. 3
	adc a,033h		;1f1c	ce 33		. 3
	and c			;1f1e	a1		.
	ld sp,03193h		;1f1f	31 93 31	1 . 1
l1f22h:
	ld h,b			;1f22	60		`
l1f23h:
	ld sp,030f9h		;1f23	31 f9 30	1 . 0
	jp (hl)			;1f26	e9		.
	jr nc,l1f0fh		;1f27	30 e6		0 .
	jr nc,l1f84h		;1f29	30 59		0 Y
	jr nc,$-62		;1f2b	30 c0		0 .
	cpl			;1f2d	2f		/
	xor a			;1f2e	af		.
	cpl			;1f2f	2f		/
	cp l			;1f30	bd		.
	ld l,074h		;1f31	2e 74		. t
	ld l,070h		;1f33	2e 70		. p
	ld l,070h		;1f35	2e 70		. p
	inc l			;1f37	2c		,
	jp p,0e529h		;1f38	f2 29 e5	. ) .
	add hl,hl		;1f3b	29		)
	or (hl)			;1f3c	b6		.
	add hl,hl		;1f3d	29		)
	rst 10h			;1f3e	d7		.
	jr z,l1ecfh		;1f3f	28 8e		( .
	jr z,l1f97h		;1f41	28 54		( T
	jr z,$+18		;1f43	28 10		( .
	jr z,l1f22h		;1f45	28 db		( .
	ld h,079h		;1f47	26 79		& y
	ld h,060h		;1f49	26 60		& `
	ld h,03eh		;1f4b	26 3e		& >
	ld h,035h		;1f4d	26 35		& 5
	ld h,003h		;1f4f	26 03		& .
	ld h,01dh		;1f51	26 1d		& .
	inc h			;1f53	24		$
	sbc a,023h		;1f54	de 23		. #
	add a,b			;1f56	80		.
	inc hl			;1f57	23		#
	ld l,e			;1f58	6b		k
	ld (0222bh),hl		;1f59	22 2b 22	" + "
	ld a,(hl)		;1f5c	7e		~
	ld hl,02159h		;1f5d	21 59 21	! Y !
	ld d,l			;1f60	55		U
	ld hl,0201dh		;1f61	21 1d 20	! .  
	add hl,bc		;1f64	09		.
	jr nz,$-19		;1f65	20 eb		  .
	rra			;1f67	1f		.
	call nc,0bb1fh		;1f68	d4 1f bb	. . .
	rra			;1f6b	1f		.
	sbc a,c			;1f6c	99		.
	rra			;1f6d	1f		.
	add hl,sp		;1f6e	39		9
	rra			;1f6f	1f		.
	ld (hl),01fh		;1f70	36 1f		6 .
	inc hl			;1f72	23		#
	rra			;1f73	1f		.
	ld e,01fh		;1f74	1e 1f		. .
	pop af			;1f76	f1		.
	ld e,0e4h		;1f77	1e e4		. .
	ld e,0d4h		;1f79	1e d4		. .
	ld e,0cah		;1f7b	1e ca		. .
	ld e,082h		;1f7d	1e 82		. .
	ld e,097h		;1f7f	1e 97		. .
	dec e			;1f81	1d		.
	ld d,l			;1f82	55		U
	dec e			;1f83	1d		.
l1f84h:
	ld e,c			;1f84	59		Y
	inc e			;1f85	1c		.
	ld a,b			;1f86	78		x
	inc e			;1f87	1c		.
	ret c			;1f88	d8		.
	ld a,(de)		;1f89	1a		.
	daa			;1f8a	27		'
	ld a,(de)		;1f8b	1a		.
	adc a,b			;1f8c	88		.
	rla			;1f8d	17		.
	ld d,b			;1f8e	50		P
	rla			;1f8f	17		.
	jr nz,l1fa9h		;1f90	20 17		  .
	ret p			;1f92	f0		.
	ld d,0d6h		;1f93	16 d6		. .
	ld d,00dh		;1f95	16 0d		. .
l1f97h:
	ld d,0d0h		;1f97	16 d0		. .
	dec h			;1f99	25		%
	call z,0d425h		;1f9a	cc 25 d4	. % .
	dec h			;1f9d	25		%
	ret z			;1f9e	c8		.
	dec h			;1f9f	25		%
	ld h,l			;1fa0	65		e
	inc d			;1fa1	14		.
	ld hl,(0be14h)		;1fa2	2a 14 be	* . .
	inc de			;1fa5	13		.
	sbc a,a			;1fa6	9f		.
	inc de			;1fa7	13		.
	ld d,h			;1fa8	54		T
l1fa9h:
	inc de			;1fa9	13		.
	cp e			;1faa	bb		.
	ld (de),a		;1fab	12		.
	jr nc,l1fc0h		;1fac	30 12		0 .
	pop hl			;1fae	e1		.
	ld de,l0d31h		;1faf	11 31 0d	. 1 .
	dec e			;1fb2	1d		.
	dec c			;1fb3	0d		.
	dec c			;1fb4	0d		.
	dec c			;1fb5	0d		.
	ld c,d			;1fb6	4a		J
	ld a,(bc)		;1fb7	0a		.
	inc hl			;1fb8	23		#
	ld a,(bc)		;1fb9	0a		.
	jp pe,0a908h		;1fba	ea 08 a9	. . .
	ex af,af'		;1fbd	08		.
	adc a,b			;1fbe	88		.
	ex af,af'		;1fbf	08		.
l1fc0h:
	djnz $+9		;1fc0	10 07		. .
	or d			;1fc2	b2		.
	dec b			;1fc3	05		.
	nop			;1fc4	00		.
	dec b			;1fc5	05		.
	ld (bc),a		;1fc6	02		.
	ld a,(bc)		;1fc7	0a		.
	ld (hl),004h		;1fc8	36 04		6 .
	di			;1fca	f3		.
	inc bc			;1fcb	03		.
	pop hl			;1fcc	e1		.
	ld (bc),a		;1fcd	02		.
	rst 38h			;1fce	ff		.
	rst 38h			;1fcf	ff		.
	rst 38h			;1fd0	ff		.
	rst 38h			;1fd1	ff		.
	rst 38h			;1fd2	ff		.
	rst 38h			;1fd3	ff		.
	rst 38h			;1fd4	ff		.
	rst 38h			;1fd5	ff		.
	rst 38h			;1fd6	ff		.
	rst 38h			;1fd7	ff		.
	ld hl,0cf67h		;1fd8	21 67 cf	! g .
	ld h,l			;1fdb	65		e
	ld (hl),c		;1fdc	71		q
	ld h,l			;1fdd	65		e
	sbc a,c			;1fde	99		.
	ld h,h			;1fdf	64		d
	ld e,(hl)		;1fe0	5e		^
	ld h,h			;1fe1	64		d
	dec b			;1fe2	05		.
	ld h,h			;1fe3	64		d
	rst 38h			;1fe4	ff		.
	rst 38h			;1fe5	ff		.
	rst 38h			;1fe6	ff		.
	rst 38h			;1fe7	ff		.
	rst 38h			;1fe8	ff		.
	rst 38h			;1fe9	ff		.
	rst 38h			;1fea	ff		.
	rst 38h			;1feb	ff		.
	push hl			;1fec	e5		.
	nop			;1fed	00		.
	and e			;1fee	a3		.
	ld c,051h		;1fef	0e 51		. Q
	ex af,af'		;1ff1	08		.
	push hl			;1ff2	e5		.
	ld b,0cch		;1ff3	06 cc		. .
	dec b			;1ff5	05		.
	xor e			;1ff6	ab		.
	ld bc,sub_018dh		;1ff7	01 8d 01	. . .
	adc a,c			;1ffa	89		.
	ld bc,sub_00fch		;1ffb	01 fc 00	. . .
	ld l,b			;1ffe	68		h
l1fffh:
	nop			;1fff	00		.
