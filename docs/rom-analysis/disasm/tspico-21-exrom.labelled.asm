; z80dasm 1.2.0
; command line: z80dasm -a -l -t -g 0x0000 -S docs/rom-analysis/disasm/tspico-21-exrom-symbols.sym -o docs/rom-analysis/disasm/tspico-21-exrom.labelled.asm /var/folders/g_/g7fbfjh557g6jk0qzzghq8p40000gn/T/tmp.tpglAkPkAv/exrom.bin

	org 00000h
CH_ALLOC:	equ 0x0200
H_MAKE_ROOM:	equ 0x12bb
H_EXPT_1NUM:	equ 0x1be5
H_TEST_ROOM:	equ 0x1fbb
BIOS_WF_NPH:	equ 0x239e
SKIP_SPACES:	equ 0x3149
LOWER_LOOP:	equ 0x334f

l0000h:
	di			;0000	f3		.
l0001h:
	jr BOOT_MAP_16K		;0001	18 46		. F
l0003h:
	jp l1cbch		;0003	c3 bc 1c	. . .
l0006h:
	rst 38h			;0006	ff		.
l0007h:
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
l0021h:
	ld a,(05cc2h)		;0021	3a c2 5c	: . \
	and a			;0024	a7		.
	ei			;0025	fb		.
	jr z,l002ch		;0026	28 04		( .
	pop af			;0028	f1		.
l0029h:
	call 0fd32h		;0029	cd 32 fd	. 2 .
l002ch:
	pop af			;002c	f1		.
	call 06572h		;002d	cd 72 65	. r e
l0030h:
	rst 38h			;0030	ff		.
	rst 38h			;0031	ff		.
	rst 38h			;0032	ff		.
	ld bc,0ad05h		;0033	01 05 ad	. . .
	rlca			;0036	07		.
	inc sp			;0037	33		3
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
BOOT_MAP_16K:
	ld a,003h		;0049	3e 03		> .
l004bh:
	out (0f4h),a		;004b	d3 f4		. .
	jr l005ah		;004d	18 0b		. .
l004fh:
	xor a			;004f	af		.
	out (0f4h),a		;0050	d3 f4		. .
	out (0ffh),a		;0052	d3 ff		. .
	ld de,0ffffh		;0054	11 ff ff	. . .
	jp l0d31h		;0057	c3 31 0d	. 1 .
l005ah:
	jp l1caeh		;005a	c3 ae 1c	. . .
	ld de,06000h		;005d	11 00 60	. . `
	ld bc,l000bh		;0060	01 0b 00	. . .
	defb 0edh ;next byte illegal after ed	;0063	ed		.
	nop			;0064	00		.
	ret			;0065	c9		.
	jr l0003h		;0066	18 9b		. .
sub_0068h:
	jp l1879h		;0068	c3 79 18	. y .
l006bh:
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
	ld bc,l3b0eh		;009c	01 0e 3b	. . ;
	ex af,af'		;009f	08		.
l00a0h:
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
RPT_D_BREAK_CONT:
	rst 8			;00f8	cf		.
	inc c			;00f9	0c		.
l00fah:
	pop af			;00fa	f1		.
	ret			;00fb	c9		.
sub_00fch:
	jp l196dh		;00fc	c3 6d 19	. m .
l00ffh:
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
	ld hl,l0414h+1		;0117	21 15 04	! . .
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
	jp l0210h		;01ab	c3 10 02	. . .
l01aeh:
	ld bc,019e1h		;01ae	01 e1 19	. . .
	sub c			;01b1	91		.
	ld (05c74h),a		;01b2	32 74 5c	2 t \
	exx			;01b5	d9		.
	ld hl,l254fh		;01b6	21 4f 25	! O %
	jp l08ddh		;01b9	c3 dd 08	. . .
l01bch:
	call sub_221fh		;01bc	cd 1f 22	. . "
	xor a			;01bf	af		.
	jp l03f6h		;01c0	c3 f6 03	. . .
READ_STATUS_AND_OPEN:
	call READ_STATUS_BYTE	;01c3	cd b9 02	. . .
	jp OPEN_MAIN_SCREEN	;01c6	c3 f1 04	. . .
l01c9h:
	jp CALL_HOME		;01c9	c3 dd 03	. . .
	bit 7,(iy+001h)		;01cc	fd cb 01 7e	. . . ~
	jr z,l0238h		;01d0	28 66		( f
	jp F_HOOK_VEC		;01d2	c3 03 30	. . 0
SAVE_ETC_BODY:
	ld a,(05c74h)		;01d5	3a 74 5c	: t \
	and a			;01d8	a7		.
	jr z,l01ddh		;01d9	28 02		( .
	ld c,022h		;01db	0e 22		. "
l01ddh:
	call sub_01e2h		;01dd	cd e2 01	. . .
	jr l01f4h		;01e0	18 12		. .
sub_01e2h:
	push ix			;01e2	dd e5		. .
	exx			;01e4	d9		.
	ld hl,l0030h		;01e5	21 30 00	! 0 .
	jr l01c9h		;01e8	18 df		. .
l01eah:
	exx			;01ea	d9		.
	ld hl,l24c7h		;01eb	21 c7 24	! . $
	jp l08ddh		;01ee	c3 dd 08	. . .
	nop			;01f1	00		.
	nop			;01f2	00		.
	nop			;01f3	00		.
l01f4h:
	push de			;01f4	d5		.
	pop ix			;01f5	dd e1		. .
	ld b,00bh		;01f7	06 0b		. .
	ld a,020h		;01f9	3e 20		>  
l01fbh:
	ld (de),a		;01fb	12		.
	inc de			;01fc	13		.
	djnz l01fbh		;01fd	10 fc		. .
l01ffh:
	ld (ix+001h),0ffh	;01ff	dd 36 01 ff	. 6 . .
	call sub_0208h		;0203	cd 08 02	. . .
	jr l021ah		;0206	18 12		. .
sub_0208h:
	push ix			;0208	dd e5		. .
	exx			;020a	d9		.
	ld hl,l2fafh		;020b	21 af 2f	! . /
	jr l01c9h		;020e	18 b9		. .
l0210h:
	ld hl,l01eah		;0210	21 ea 01	! . .
	push hl			;0213	e5		.
	ld a,(05c74h)		;0214	3a 74 5c	: t \
	jp l01aeh		;0217	c3 ae 01	. . .
l021ah:
	ld hl,0fff6h		;021a	21 f6 ff	! . .
	dec bc			;021d	0b		.
	add hl,bc		;021e	09		.
	inc bc			;021f	03		.
	jr nc,l0231h		;0220	30 0f		0 .
	ld a,(05c74h)		;0222	3a 74 5c	: t \
	and a			;0225	a7		.
	jr nz,$+4		;0226	20 02		  .
l0228h:
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
	call sub_023dh		;0238	cd 3d 02	. = .
	jr l024fh		;023b	18 12		. .
sub_023dh:
	push ix			;023d	dd e5		. .
	exx			;023f	d9		.
	ld hl,l0017h+1		;0240	21 18 00	! . .
	jr l01c9h		;0243	18 84		. .
	exx			;0245	d9		.
	ld hl,l0008h		;0246	21 08 00	! . .
	jp l08ddh		;0249	c3 dd 08	. . .
	nop			;024c	00		.
	nop			;024d	00		.
	nop			;024e	00		.
l024fh:
	cp 0e4h			;024f	fe e4		. .
	jp nz,l02f2h		;0251	c2 f2 02	. . .
	ld a,(05c74h)		;0254	3a 74 5c	: t \
	cp 003h			;0257	fe 03		. .
	jp z,l08d9h		;0259	ca d9 08	. . .
	jr l0280h		;025c	18 22		. "
GET_STATUS_BIT_0:
	call sub_03c1h		;025e	cd c1 03	. . .
	inc de			;0261	13		.
	ld a,d			;0262	7a		z
	or e			;0263	b3		.
	ld a,001h		;0264	3e 01		> .
	ret z			;0266	c8		.
	ld a,000h		;0267	3e 00		> .
	ret			;0269	c9		.
GET_STATUS_BIT_1:
	nop			;026a	00		.
	nop			;026b	00		.
	nop			;026c	00		.
	xor a			;026d	af		.
	ret			;026e	c9		.
FN_CHAIN_HEAD:
	cp 080h			;026f	fe 80		. .
	jp nz,FN_CHAIN_C1	;0271	c2 94 21	. . !
FN_81_PRINT_STRING:
	call READ_STATUS_BYTE	;0274	cd b9 02	. . .
	call OPEN_MAIN_SCREEN	;0277	cd f1 04	. . .
	jp PRINT_STRING_FROM_PICO	;027a	c3 5f 04	. _ .
	nop			;027d	00		.
	nop			;027e	00		.
	nop			;027f	00		.
l0280h:
	call sub_02d7h		;0280	cd d7 02	. . .
	call sub_02e0h		;0283	cd e0 02	. . .
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
l02a0h:
	ld (ix+00bh),a		;02a0	dd 77 0b	. w .
	inc hl			;02a3	23		#
	ld a,(hl)		;02a4	7e		~
	ld (ix+00ch),a		;02a5	dd 77 0c	. w .
	inc hl			;02a8	23		#
l02a9h:
	ld (ix+00eh),c		;02a9	dd 71 0e	. q .
	ld a,001h		;02ac	3e 01		> .
	bit 6,c			;02ae	cb 71		. q
l02b0h:
	jr z,l02b3h		;02b0	28 01		( .
	inc a			;02b2	3c		<
l02b3h:
	ld (ix+000h),a		;02b3	dd 77 00	. w .
l02b6h:
	ex de,hl		;02b6	eb		.
	jr l02cbh		;02b7	18 12		. .
READ_STATUS_BYTE:
	call TSPICO_READ_DATA	;02b9	cd 98 22	. . "
	jp c,l192fh		;02bc	da 2f 19	. / .
	and a			;02bf	a7		.
	jp z,l192fh		;02c0	ca 2f 19	. / .
	dec a			;02c3	3d		=
	ret z			;02c4	c8		.
	scf			;02c5	37		7
	ret			;02c6	c9		.
	nop			;02c7	00		.
	nop			;02c8	00		.
	nop			;02c9	00		.
	nop			;02ca	00		.
l02cbh:
	call sub_02d7h		;02cb	cd d7 02	. . .
	cp 029h			;02ce	fe 29		. )
	jr nz,$-59		;02d0	20 c3		  .
	call sub_02d7h		;02d2	cd d7 02	. . .
	jr l02e9h		;02d5	18 12		. .
sub_02d7h:
	push ix			;02d7	dd e5		. .
	exx			;02d9	d9		.
	ld hl,l0020h		;02da	21 20 00	!   .
	jp CALL_HOME		;02dd	c3 dd 03	. . .
sub_02e0h:
	push ix			;02e0	dd e5		. .
	exx			;02e2	d9		.
	ld hl,l2c70h		;02e3	21 70 2c	! p ,
	jp CALL_HOME		;02e6	c3 dd 03	. . .
l02e9h:
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
	call sub_02d7h		;02fe	cd d7 02	. . .
	jr l0315h		;0301	18 12		. .
sub_0303h:
	push ix			;0303	dd e5		. .
	exx			;0305	d9		.
	ld hl,l0017h+1		;0306	21 18 00	! . .
	jp CALL_HOME		;0309	c3 dd 03	. . .
sub_030ch:
	push ix			;030c	dd e5		. .
	exx			;030e	d9		.
	ld hl,l0010h		;030f	21 10 00	! . .
	jp CALL_HOME		;0312	c3 dd 03	. . .
l0315h:
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
	call BANK_SWITCH	;034d	cd 99 0f	. . .
	exx			;0350	d9		.
	ld hl,YN_LOOP		;0351	21 e7 21	! . !
	push hl			;0354	e5		.
	ld l,000h		;0355	2e 00		. .
	ld h,0ffh		;0357	26 ff		& .
	push hl			;0359	e5		.
	ld hl,l0000h		;035a	21 00 00	! . .
	push hl			;035d	e5		.
	push hl			;035e	e5		.
	exx			;035f	d9		.
	call BANK_SWITCH	;0360	cd 99 0f	. . .
	pop ix			;0363	dd e1		. .
	jr nz,l0387h		;0365	20 20		   
	ld a,(05c74h)		;0367	3a 74 5c	: t \
	and a			;036a	a7		.
	jp z,l08d9h		;036b	ca d9 08	. . .
	call sub_0373h		;036e	cd 73 03	. s .
	jr l0385h		;0371	18 12		. .
sub_0373h:
	push ix			;0373	dd e5		. .
	exx			;0375	d9		.
	ld hl,01c51h		;0376	21 51 1c	! Q .
	jp CALL_HOME		;0379	c3 dd 03	. . .
sub_037ch:
	push ix			;037c	dd e5		. .
	exx			;037e	d9		.
	ld hl,H_FIND_INT2	;037f	21 23 1f	! # .
	jp CALL_HOME		;0382	c3 dd 03	. . .
l0385h:
	jr l03bch		;0385	18 35		. 5
l0387h:
	push ix			;0387	dd e5		. .
	push ix			;0389	dd e5		. .
	call sub_0392h		;038b	cd 92 03	. . .
	pop ix			;038e	dd e1		. .
	jr l039ch		;0390	18 0a		. .
sub_0392h:
	exx			;0392	d9		.
	ld hl,l2558h		;0393	21 58 25	! X %
	jp l08ddh		;0396	c3 dd 08	. . .
	nop			;0399	00		.
	nop			;039a	00		.
	nop			;039b	00		.
l039ch:
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
	call BANK_SWITCH	;03ac	cd 99 0f	. . .
	pop ix			;03af	dd e1		. .
	cp 02ch			;03b1	fe 2c		. ,
	jr z,l03d5h		;03b3	28 20		(  
	ld a,(05c74h)		;03b5	3a 74 5c	: t \
	and a			;03b8	a7		.
	jp z,l08d9h		;03b9	ca d9 08	. . .
l03bch:
	call sub_0373h		;03bc	cd 73 03	. s .
	jr l03d3h		;03bf	18 12		. .
sub_03c1h:
	push ix			;03c1	dd e5		. .
	exx			;03c3	d9		.
	ld hl,l02b0h		;03c4	21 b0 02	! . .
	jp CALL_HOME		;03c7	c3 dd 03	. . .
sub_03cah:
	push ix			;03ca	dd e5		. .
	exx			;03cc	d9		.
	ld hl,H_EXPT_1NUM	;03cd	21 e5 1b	! . .
	jp CALL_HOME		;03d0	c3 dd 03	. . .
l03d3h:
	jr l03ffh		;03d3	18 2a		. *
l03d5h:
	call sub_02d7h		;03d5	cd d7 02	. . .
	call sub_03cah		;03d8	cd ca 03	. . .
	jr l03ffh		;03db	18 22		. "
CALL_HOME:
EX_TO_HOME:
	push hl			;03dd	e5		.
	ld hl,0ff00h		;03de	21 00 ff	! . .
	push hl			;03e1	e5		.
	ld h,000h		;03e2	26 00		& .
	push hl			;03e4	e5		.
	push hl			;03e5	e5		.
	exx			;03e6	d9		.
	call BANK_SWITCH	;03e7	cd 99 0f	. . .
	pop ix			;03ea	dd e1		. .
	ret			;03ec	c9		.
EX_PO_MSG:
	push ix			;03ed	dd e5		. .
	exx			;03ef	d9		.
	ld hl,l073fh		;03f0	21 3f 07	! ? .
	jp CALL_HOME		;03f3	c3 dd 03	. . .
l03f6h:
	ld a,0ffh		;03f6	3e ff		> .
	ld (05dcfh),a		;03f8	32 cf 5d	2 . ]
	jp l1c49h		;03fb	c3 49 1c	. I .
	nop			;03fe	00		.
l03ffh:
	bit 7,(iy+001h)		;03ff	fd cb 01 7e	. . . ~
	ret z			;0403	c8		.
	push ix			;0404	dd e5		. .
	call sub_040dh		;0406	cd 0d 04	. . .
	pop ix			;0409	dd e1		. .
	jr l041bh		;040b	18 0e		. .
sub_040dh:
	exx			;040d	d9		.
	ld hl,l3cdch		;040e	21 dc 3c	! . <
	jp l08ddh		;0411	c3 dd 08	. . .
l0414h:
	ld a,009h		;0414	3e 09		> .
l0416h:
	scf			;0416	37		7
	ret			;0417	c9		.
	nop			;0418	00		.
	nop			;0419	00		.
	nop			;041a	00		.
l041bh:
	ld (ix+00bh),c		;041b	dd 71 0b	. q .
	ld (ix+00ch),b		;041e	dd 70 0c	. p .
	call sub_037ch		;0421	cd 7c 03	. | .
	jr l0438h		;0424	18 12		. .
OPEN_STREAM:
	push ix			;0426	dd e5		. .
	exx			;0428	d9		.
	ld hl,H_CHAN_OPEN	;0429	21 30 12	! 0 .
	jp CALL_HOME		;042c	c3 dd 03	. . .
sub_042fh:
	push ix			;042f	dd e5		. .
	exx			;0431	d9		.
	ld hl,l2fafh		;0432	21 af 2f	! . /
	jp CALL_HOME		;0435	c3 dd 03	. . .
l0438h:
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
	jr l0481h		;045d	18 22		. "
PRINT_STRING_FROM_PICO:
	push af			;045f	f5		.
	jr l0465h		;0460	18 03		. .
l0462h:
	call sub_05fah		;0462	cd fa 05	. . .
l0465h:
	call sub_068eh		;0465	cd 8e 06	. . .
	jr c,l046dh		;0468	38 03		8 .
	jp l06f2h		;046a	c3 f2 06	. . .
l046dh:
	pop af			;046d	f1		.
	and a			;046e	a7		.
	ret			;046f	c9		.
	nop			;0470	00		.
GET_KEY_AND_SEND:
	call sub_03c1h		;0471	cd c1 03	. . .
	inc de			;0474	13		.
	ld a,d			;0475	7a		z
	or e			;0476	b3		.
	jr nz,GET_KEY_AND_SEND	;0477	20 f8		  .
l0479h:
	call KEYWAIT		;0479	cd 46 23	. F #
	jr z,l0479h		;047c	28 fb		( .
	jp SEND_KEY		;047e	c3 40 1c	. @ .
l0481h:
	call sub_02d7h		;0481	cd d7 02	. . .
	call sub_03cah		;0484	cd ca 03	. . .
	bit 7,(iy+001h)		;0487	fd cb 01 7e	. . . ~
	ret z			;048b	c8		.
	push ix			;048c	dd e5		. .
	exx			;048e	d9		.
	ld hl,H_FIND_INT2	;048f	21 23 1f	! # .
	push hl			;0492	e5		.
	ld l,000h		;0493	2e 00		. .
	ld h,0ffh		;0495	26 ff		& .
	push hl			;0497	e5		.
	ld hl,l0000h		;0498	21 00 00	! . .
	push hl			;049b	e5		.
	push hl			;049c	e5		.
	exx			;049d	d9		.
	call BANK_SWITCH	;049e	cd 99 0f	. . .
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
	jr l04fah		;04e6	18 12		. .
sub_04e8h:
	push hl			;04e8	e5		.
	ld hl,l0000h		;04e9	21 00 00	! . .
	ld (05dd1h),hl		;04ec	22 d1 5d	" . ]
	pop hl			;04ef	e1		.
	ret			;04f0	c9		.
OPEN_MAIN_SCREEN:
	push af			;04f1	f5		.
	ld a,0feh		;04f2	3e fe		> .
	call OPEN_STREAM	;04f4	cd 26 04	. & .
	pop af			;04f7	f1		.
	ret			;04f8	c9		.
	nop			;04f9	00		.
l04fah:
	call OPEN_STREAM	;04fa	cd 26 04	. & .
	ld (iy+052h),003h	;04fd	fd 36 52 03	. 6 R .
	ld c,080h		;0501	0e 80		. .
	ld a,(ix+000h)		;0503	dd 7e 00	. ~ .
	cp (ix-011h)		;0506	dd be ef	. . .
	jr nz,l050dh		;0509	20 02		  .
	ld c,0f6h		;050b	0e f6		. .
l050dh:
	cp 004h			;050d	fe 04		. .
	jr nc,l04d6h		;050f	30 c5		0 .
	ld de,l3ca8h		;0511	11 a8 3c	. . <
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
	call BANK_SWITCH	;0527	cd 99 0f	. . .
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
	jr l0558h		;0544	18 12		. .
POLL_KEYPRESS:
	res 5,(iy+001h)		;0546	fd cb 01 ae	. . . .
	set 3,(iy+001h)		;054a	fd cb 01 de	. . . .
	call sub_03c1h		;054e	cd c1 03	. . .
	xor a			;0551	af		.
	bit 5,(iy+001h)		;0552	fd cb 01 6e	. . . n
	jr l0566h		;0556	18 0e		. .
l0558h:
	call sub_030ch		;0558	cd 0c 03	. . .
	djnz l053dh		;055b	10 e0		. .
	bit 7,c			;055d	cb 79		. y
	jp nz,l04d6h		;055f	c2 d6 04	. . .
	ld a,00dh		;0562	3e 0d		> .
	jr l0578h		;0564	18 12		. .
l0566h:
	ret z			;0566	c8		.
	ld a,(05c08h)		;0567	3a 08 5c	: . \
	and 07fh		;056a	e6 7f		. .
	cp 061h			;056c	fe 61		. a
	ret c			;056e	d8		.
	cp 07bh			;056f	fe 7b		. {
	ret nc			;0571	d0		.
	and 0dfh		;0572	e6 df		. .
	ret			;0574	c9		.
	nop			;0575	00		.
	nop			;0576	00		.
	nop			;0577	00		.
l0578h:
	call sub_030ch		;0578	cd 0c 03	. . .
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
	ld de,l0003h+2		;05e9	11 05 00	. . .
	add hl,de		;05ec	19		.
	ld b,h			;05ed	44		D
	ld c,l			;05ee	4d		M
	jr l0603h		;05ef	18 12		. .
sub_05f1h:
	push ix			;05f1	dd e5		. .
	exx			;05f3	d9		.
	ld hl,H_TEST_ROOM	;05f4	21 bb 1f	! . .
	jp CALL_HOME		;05f7	c3 dd 03	. . .
sub_05fah:
	ld (iy+052h),0ffh	;05fa	fd 36 52 ff	. 6 R .
	jp sub_030ch		;05fe	c3 0c 03	. . .
	nop			;0601	00		.
	nop			;0602	00		.
l0603h:
	call sub_05f1h		;0603	cd f1 05	. . .
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
l0619h:
	ld (05c5fh),ix		;0619	dd 22 5f 5c	. " _ \
	push ix			;061d	dd e5		. .
	exx			;061f	d9		.
	ld hl,H_RECLAIM		;0620	21 50 17	! P .
	push hl			;0623	e5		.
	ld l,000h		;0624	2e 00		. .
	ld h,0ffh		;0626	26 ff		& .
	push hl			;0628	e5		.
	ld hl,l0000h		;0629	21 00 00	! . .
	push hl			;062c	e5		.
	push hl			;062d	e5		.
	exx			;062e	d9		.
	call BANK_SWITCH	;062f	cd 99 0f	. . .
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
	jr l065eh		;064a	18 12		. .
sub_064ch:
	push ix			;064c	dd e5		. .
	exx			;064e	d9		.
	ld hl,H_MAKE_ROOM	;064f	21 bb 12	! . .
	jp CALL_HOME		;0652	c3 dd 03	. . .
READ_STATUS:
	call CHECK_BREAK	;0655	cd 9f 06	. . .
	jp nc,BREAK_ABORT	;0658	d2 aa 06	. . .
	in a,(00fh)		;065b	db 0f		. .
	ret			;065d	c9		.
l065eh:
	call sub_064ch		;065e	cd 4c 06	. L .
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
	jr l0697h		;0683	18 12		. .
sub_0685h:
	push ix			;0685	dd e5		. .
	exx			;0687	d9		.
	ld hl,0174dh		;0688	21 4d 17	! M .
	jp CALL_HOME		;068b	c3 dd 03	. . .
sub_068eh:
	call TSPICO_READ_DATA	;068e	cd 98 22	. . "
	and a			;0691	a7		.
	ret z			;0692	c8		.
	cp 080h			;0693	fe 80		. .
	ccf			;0695	3f		?
	ret			;0696	c9		.
l0697h:
	call sub_0685h		;0697	cd 85 06	. . .
	pop bc			;069a	c1		.
	push hl			;069b	e5		.
	push bc			;069c	c5		.
	jr l06b1h		;069d	18 12		. .
CHECK_BREAK:
	call sub_0856h		;069f	cd 56 08	. V .
	rra			;06a2	1f		.
	ret c			;06a3	d8		.
	ld a,0feh		;06a4	3e fe		> .
	in a,(0feh)		;06a6	db fe		. .
	rra			;06a8	1f		.
	ret			;06a9	c9		.
BREAK_ABORT:
	jp BRK_ABORT		;06aa	c3 1e 23	. . #
	nop			;06ad	00		.
	nop			;06ae	00		.
	nop			;06af	00		.
	nop			;06b0	00		.
l06b1h:
	call sub_064ch		;06b1	cd 4c 06	. L .
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
	call sub_01e2h		;06ed	cd e2 01	. . .
	jr l0704h		;06f0	18 12		. .
l06f2h:
	jp z,l046dh		;06f2	ca 6d 04	. m .
	cp 003h			;06f5	fe 03		. .
	jp z,l21fah		;06f7	ca fa 21	. . !
	jp l0462h		;06fa	c3 62 04	. b .
l06fdh:
	ld hl,00a30h		;06fd	21 30 0a	! 0 .
	jp l16dfh		;0700	c3 df 16	. . .
	nop			;0703	00		.
l0704h:
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
	call BANK_SWITCH	;073c	cd 99 0f	. . .
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
	call BANK_SWITCH	;076d	cd 99 0f	. . .
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
	call BANK_SWITCH	;07b2	cd 99 0f	. . .
	exx			;07b5	d9		.
	ld hl,H_RECLAIM		;07b6	21 50 17	! P .
	push hl			;07b9	e5		.
	ld l,000h		;07ba	2e 00		. .
	ld h,0ffh		;07bc	26 ff		& .
	push hl			;07be	e5		.
	ld hl,l0000h		;07bf	21 00 00	! . .
	push hl			;07c2	e5		.
	push hl			;07c3	e5		.
	exx			;07c4	d9		.
	call BANK_SWITCH	;07c5	cd 99 0f	. . .
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
	call BANK_SWITCH	;07e3	cd 99 0f	. . .
	pop ix			;07e6	dd e1		. .
	ld (05c5fh),hl		;07e8	22 5f 5c	" _ \
	ld hl,(05c53h)		;07eb	2a 53 5c	* S \
	ex (sp),hl		;07ee	e3		.
	push bc			;07ef	c5		.
	ex af,af'		;07f0	08		.
	jr c,l080eh		;07f1	38 1b		8 .
	dec hl			;07f3	2b		+
	jr l0808h		;07f4	18 12		. .
sub_07f6h:
	push bc			;07f6	c5		.
	ld b,006h		;07f7	06 06		. .
l07f9h:
	push bc			;07f9	c5		.
	ld b,000h		;07fa	06 00		. .
l07fch:
	ld a,07fh		;07fc	3e 7f		> .
	djnz l07fch		;07fe	10 fc		. .
	pop bc			;0800	c1		.
	djnz l07f9h		;0801	10 f6		. .
	pop bc			;0803	c1		.
	in a,(0feh)		;0804	db fe		. .
	ret			;0806	c9		.
	nop			;0807	00		.
l0808h:
	call sub_064ch		;0808	cd 4c 06	. L .
	inc hl			;080b	23		#
	jr l0825h		;080c	18 17		. .
l080eh:
	jr l0822h		;080e	18 12		. .
LOOP_EXIT_OK:
	call sub_05fah		;0810	cd fa 05	. . .
LOOP_EXIT_ERR:
	pop af			;0813	f1		.
	ret			;0814	c9		.
l0815h:
	ld a,002h		;0815	3e 02		> .
	call sub_1924h		;0817	cd 24 19	. $ .
	and a			;081a	a7		.
	ei			;081b	fb		.
	ret			;081c	c9		.
sub_081dh:
	ld a,002h		;081d	3e 02		> .
	jp l1862h		;081f	c3 62 18	. b .
l0822h:
	call sub_064ch		;0822	cd 4c 06	. L .
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
	ld hl,H_RECLAIM		;083b	21 50 17	! P .
	push hl			;083e	e5		.
	ld l,000h		;083f	2e 00		. .
	ld h,0ffh		;0841	26 ff		& .
	push hl			;0843	e5		.
	ld hl,l0000h		;0844	21 00 00	! . .
	push hl			;0847	e5		.
	push hl			;0848	e5		.
	exx			;0849	d9		.
	call BANK_SWITCH	;084a	cd 99 0f	. . .
	pop ix			;084d	dd e1		. .
	pop de			;084f	d1		.
	ret			;0850	c9		.
l0851h:
	push hl			;0851	e5		.
	ld a,0fdh		;0852	3e fd		> .
	jr l0868h		;0854	18 12		. .
sub_0856h:
	push bc			;0856	c5		.
	ld b,00ah		;0857	06 0a		. .
l0859h:
	call sub_07f6h		;0859	cd f6 07	. . .
	djnz l0859h		;085c	10 fb		. .
	pop bc			;085e	c1		.
	ret			;085f	c9		.
	nop			;0860	00		.
	nop			;0861	00		.
	nop			;0862	00		.
	nop			;0863	00		.
	nop			;0864	00		.
	nop			;0865	00		.
	nop			;0866	00		.
	nop			;0867	00		.
l0868h:
	call OPEN_STREAM	;0868	cd 26 04	. & .
	xor a			;086b	af		.
	ld de,l3c89h		;086c	11 89 3c	. . <
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
	call BANK_SWITCH	;0881	cd 99 0f	. . .
	pop ix			;0884	dd e1		. .
	call sub_22aeh		;0886	cd ae 22	. . "
	jr c,l088dh		;0889	38 02		8 .
	rst 8			;088b	cf		.
	inc c			;088c	0c		.
l088dh:
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
l08beh:
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
	call BANK_SWITCH	;08d0	cd 99 0f	. . .
	pop ix			;08d3	dd e1		. .
	pop de			;08d5	d1		.
	pop bc			;08d6	c1		.
	pop af			;08d7	f1		.
	ret			;08d8	c9		.
l08d9h:
	exx			;08d9	d9		.
	ld hl,01bedh		;08da	21 ed 1b	! . .
l08ddh:
	push hl			;08dd	e5		.
	ld l,000h		;08de	2e 00		. .
	ld h,0ffh		;08e0	26 ff		& .
	push hl			;08e2	e5		.
	exx			;08e3	d9		.
l08e4h:
	call sub_0f8ah		;08e4	cd 8a 0f	. . .
l08e7h:
	jp l01bch		;08e7	c3 bc 01	. . .
l08eah:
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
l0918h:
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
	ld de,l0003h+2		;093f	11 05 00	. . .
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
	ld hl,018c6h		;095e	21 c6 18	! . .
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
	ld de,l0003h+2		;09d0	11 05 00	. . .
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
	ld de,l0003h+1		;0a0c	11 04 00	. . .
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
	call sub_2082h		;0ad4	cd 82 20	. .  
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
	ld de,ENTRY_TABLE	;0afc	11 00 20	. .  
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
	ld de,l0003h+1		;0c2a	11 04 00	. . .
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
	ld de,H_RECLAIM		;0f28	11 50 17	. P .
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
	call sub_2569h		;0f47	cd 69 25	. i %
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
HOME_MSG_TABLE:
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
BANK_SWITCH:
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
	call sub_02e0h+1	;10ef	cd e1 02	. . .
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
	ld hl,(05d37h)		;1109	2a 37 5d	* 7 ]
	ld a,h			;110c	7c		|
	or l			;110d	b5		.
	jr z,l1111h		;110e	28 01		( .
	jp (hl)			;1110	e9		.
l1111h:
	pop hl			;1111	e1		.
	pop af			;1112	f1		.
	retn			;1113	ed 45		. E
HOME_MSG_SEP:
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
H_CHAN_OPEN:
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
	and 0fch		;12de	e6 fc		. .
	out (0f4h),a		;12e0	d3 f4		. .
	jr l1319h		;12e2	18 35		. 5
l12e4h:
	in a,(0f4h)		;12e4	db f4		. .
	or 003h			;12e6	f6 03		. .
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
	and 0fch		;1302	e6 fc		. .
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
	ld b,(ix+009h)		;140e	dd 46 09	. F .
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
	jr H_TRAP		;14ab	18 05		. .
l14adh:
	lddr			;14ad	ed b8		. .
	and a			;14af	a7		.
	sbc hl,bc		;14b0	ed 42		. B
H_TRAP:
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
	ld de,CH_ALLOC		;15aa	11 00 02	. . .
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
	ld a,003h		;161e	3e 03		> .
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
PRINTER_TABLE:
	jp l1781h		;1630	c3 81 17	. . .
	jp l17c3h		;1633	c3 c3 17	. . .
	jp l17cdh		;1636	c3 cd 17	. . .
	jp l1668h		;1639	c3 68 16	. h .
	jp l180fh		;163c	c3 0f 18	. . .
sub_163fh:
	push af			;163f	f5		.
	call TSPICO_WRITE_DATA	;1640	cd 9d 22	. . "
	jr c,l164ah		;1643	38 05		8 .
	xor d			;1645	aa		.
	ld d,a			;1646	57		W
	pop af			;1647	f1		.
	and a			;1648	a7		.
	ret			;1649	c9		.
l164ah:
	pop af			;164a	f1		.
	scf			;164b	37		7
	ret			;164c	c9		.
sub_164dh:
	push af			;164d	f5		.
	ld a,042h		;164e	3e 42		> B
	ld d,a			;1650	57		W
	call SYNC_WRITE		;1651	cd 00 23	. . #
	jr c,l1665h		;1654	38 0f		8 .
	pop af			;1656	f1		.
	ld (05dd9h),a		;1657	32 d9 5d	2 . ]
	call sub_163fh		;165a	cd 3f 16	. ? .
	ld a,(05dcfh)		;165d	3a cf 5d	: . ]
	call sub_163fh		;1660	cd 3f 16	. ? .
	and a			;1663	a7		.
	ret			;1664	c9		.
l1665h:
	pop af			;1665	f1		.
	scf			;1666	37		7
	ret			;1667	c9		.
l1668h:
	push af			;1668	f5		.
	ld a,005h		;1669	3e 05		> .
	call sub_164dh		;166b	cd 4d 16	. M .
	jp c,l1c20h		;166e	da 20 1c	.   .
	pop af			;1671	f1		.
	push hl			;1672	e5		.
	call sub_163fh		;1673	cd 3f 16	. ? .
	cp 080h			;1676	fe 80		. .
	jr nc,l1680h		;1678	30 06		0 .
	ld a,001h		;167a	3e 01		> .
	ld l,000h		;167c	2e 00		. .
	jr l1684h		;167e	18 04		. .
l1680h:
	ld a,002h		;1680	3e 02		> .
	ld l,008h		;1682	2e 08		. .
l1684h:
	call sub_163fh		;1684	cd 3f 16	. ? .
	ld a,(05c3ch)		;1687	3a 3c 5c	: < \
	and 010h		;168a	e6 10		. .
	bit 4,(iy+001h)		;168c	fd cb 01 66	. . . f
	jr z,l1694h		;1690	28 02		( .
	or 001h			;1692	f6 01		. .
l1694h:
	bit 1,(iy+030h)		;1694	fd cb 30 4e	. . 0 N
	jr z,l169ch		;1698	28 02		( .
	or 002h			;169a	f6 02		. .
l169ch:
	call sub_163fh		;169c	cd 3f 16	. ? .
	ld a,(05c8dh)		;169f	3a 8d 5c	: . \
	call sub_163fh		;16a2	cd 3f 16	. ? .
	ld h,000h		;16a5	26 00		& .
	ld a,l			;16a7	7d		}
	ld (05dcdh),hl		;16a8	22 cd 5d	" . ]
	call sub_163fh		;16ab	cd 3f 16	. ? .
	ld a,h			;16ae	7c		|
	call sub_163fh		;16af	cd 3f 16	. ? .
	ld a,d			;16b2	7a		z
	call TSPICO_WRITE_DATA	;16b3	cd 9d 22	. . "
	jp c,l1c20h		;16b6	da 20 1c	.   .
	ld a,l			;16b9	7d		}
	and a			;16ba	a7		.
	jr z,l16c5h		;16bb	28 08		( .
	ld hl,(05dd7h)		;16bd	2a d7 5d	* . ]
	call SEND_DATA_BLOCK_D	;16c0	cd 3e 22	. > "
	jr l16c8h		;16c3	18 03		. .
l16c5h:
	call sub_1828h		;16c5	cd 28 18	. ( .
l16c8h:
	jp c,l1bf2h		;16c8	da f2 1b	. . .
	and a			;16cb	a7		.
	jp nz,l1bf2h		;16cc	c2 f2 1b	. . .
	pop hl			;16cf	e1		.
	ld a,(05dd9h)		;16d0	3a d9 5d	: . ]
	cp 005h			;16d3	fe 05		. .
	jr nz,l16d8h		;16d5	20 01		  .
	pop af			;16d7	f1		.
l16d8h:
	xor a			;16d8	af		.
	ld (05dcdh),hl		;16d9	22 cd 5d	" . ]
	ld hl,00a35h		;16dc	21 35 0a	! 5 .
l16dfh:
	push hl			;16df	e5		.
	ld l,000h		;16e0	2e 00		. .
	ld h,0ffh		;16e2	26 ff		& .
	push hl			;16e4	e5		.
	ld hl,(05dcdh)		;16e5	2a cd 5d	* . ]
	jp l08e4h		;16e8	c3 e4 08	. . .
l16ebh:
	rlca			;16eb	07		.
	ld d,043h		;16ec	16 43		. C
	ld d,d			;16ee	52		R
	dec h			;16ef	25		%
	inc (hl)		;16f0	34		4
	ld h,c			;16f1	61		a
	ld (hl),b		;16f2	70		p
sub_16f3h:
	ld a,042h		;16f3	3e 42		> B
	ld d,a			;16f5	57		W
	call SYNC_WRITE		;16f6	cd 00 23	. . #
	ld a,000h		;16f9	3e 00		> .
	ret c			;16fb	d8		.
	ld a,(05c74h)		;16fc	3a 74 5c	: t \
	cp 0d8h			;16ff	fe d8		. .
	jr nz,l1707h		;1701	20 04		  .
	sub 0d4h		;1703	d6 d4		. .
	jr l1715h		;1705	18 0e		. .
l1707h:
	cp 0dbh			;1707	fe db		. .
	jr nz,l170fh		;1709	20 04		  .
	sub 0d6h		;170b	d6 d6		. .
	jr l1715h		;170d	18 06		. .
l170fh:
	cp 0deh			;170f	fe de		. .
	jr nz,l1715h		;1711	20 02		  .
	sub 0d8h		;1713	d6 d8		. .
l1715h:
	call sub_163fh		;1715	cd 3f 16	. ? .
	ld a,(05dcfh)		;1718	3a cf 5d	: . ]
	call sub_163fh		;171b	cd 3f 16	. ? .
	in a,(0ffh)		;171e	db ff		. .
l1720h:
	and 03fh		;1720	e6 3f		. ?
	ld b,a			;1722	47		G
	and 007h		;1723	e6 07		. .
	push af			;1725	f5		.
	ld c,0ffh		;1726	0e ff		. .
	jr z,l173ah		;1728	28 10		( .
	ld a,b			;172a	78		x
	rrca			;172b	0f		.
	rrca			;172c	0f		.
	rrca			;172d	0f		.
	and 007h		;172e	e6 07		. .
	ld hl,l16ebh		;1730	21 eb 16	! . .
	push de			;1733	d5		.
	ld e,a			;1734	5f		_
	ld d,000h		;1735	16 00		. .
	add hl,de		;1737	19		.
	pop de			;1738	d1		.
	ld c,(hl)		;1739	4e		N
l173ah:
	ld a,c			;173a	79		y
	call sub_163fh		;173b	cd 3f 16	. ? .
	pop af			;173e	f1		.
	push af			;173f	f5		.
	cp 006h			;1740	fe 06		. .
	jr nz,l1746h		;1742	20 02		  .
	ld a,003h		;1744	3e 03		> .
l1746h:
	call sub_163fh		;1746	cd 3f 16	. ? .
	ld hl,l1820h		;1749	21 20 18	!   .
	cp 003h			;174c	fe 03		. .
	jr nz,l1752h		;174e	20 02		  .
H_RECLAIM:
	ld l,040h		;1750	2e 40		. @
l1752h:
	ld a,l			;1752	7d		}
	call sub_163fh		;1753	cd 3f 16	. ? .
	ld a,h			;1756	7c		|
	call sub_163fh		;1757	cd 3f 16	. ? .
	ld hl,04000h		;175a	21 00 40	! . @
	ld (05dd3h),hl		;175d	22 d3 5d	" . ]
	pop af			;1760	f1		.
	ld hl,01b00h		;1761	21 00 1b	! . .
	jr z,l1769h		;1764	28 03		( .
	ld hl,l3b00h		;1766	21 00 3b	! . ;
l1769h:
	ld (05dcdh),hl		;1769	22 cd 5d	" . ]
	ld a,l			;176c	7d		}
	call sub_163fh		;176d	cd 3f 16	. ? .
	ld a,h			;1770	7c		|
	call sub_163fh		;1771	cd 3f 16	. ? .
	ld a,d			;1774	7a		z
	call sub_163fh		;1775	cd 3f 16	. ? .
	ld d,000h		;1778	16 00		. .
	ld hl,04000h		;177a	21 00 40	! . @
	call SEND_DATA_BLOCK_D	;177d	cd 3e 22	. > "
	ret			;1780	c9		.
l1781h:
	ld a,(05ddbh)		;1781	3a db 5d	: . ]
	and 001h		;1784	e6 01		. .
	jr z,l1794h		;1786	28 0c		( .
	call sub_16f3h		;1788	cd f3 16	. . .
	jp c,RPT_J_INVALID_IO	;178b	da 21 1c	. ! .
	and a			;178e	a7		.
	jp nz,STATUS_TO_REPORT	;178f	c2 f3 1b	. . .
	jr l17b3h		;1792	18 1f		. .
l1794h:
	di			;1794	f3		.
	ld b,0b0h		;1795	06 b0		. .
	ld hl,04000h		;1797	21 00 40	! . @
l179ah:
	push hl			;179a	e5		.
	push bc			;179b	c5		.
	call sub_17dch		;179c	cd dc 17	. . .
	pop bc			;179f	c1		.
	pop hl			;17a0	e1		.
	inc h			;17a1	24		$
	ld a,h			;17a2	7c		|
	and 007h		;17a3	e6 07		. .
	jr nz,l17b1h		;17a5	20 0a		  .
	ld a,l			;17a7	7d		}
	add a,020h		;17a8	c6 20		.  
	ld l,a			;17aa	6f		o
	ccf			;17ab	3f		?
	sbc a,a			;17ac	9f		.
	and 0f8h		;17ad	e6 f8		. .
	add a,h			;17af	84		.
	ld h,a			;17b0	67		g
l17b1h:
	djnz l179ah		;17b1	10 e7		. .
l17b3h:
	ld (05dcdh),hl		;17b3	22 cd 5d	" . ]
	jp l06fdh		;17b6	c3 fd 06	. . .
	nop			;17b9	00		.
sub_17bah:
	push ix			;17ba	dd e5		. .
	exx			;17bc	d9		.
	ld hl,00a30h		;17bd	21 30 0a	! 0 .
	jp CALL_HOME		;17c0	c3 dd 03	. . .
l17c3h:
	call sub_17dch		;17c3	cd dc 17	. . .
	exx			;17c6	d9		.
	ld hl,l0619h		;17c7	21 19 06	! . .
	jp l08ddh		;17ca	c3 dd 08	. . .
l17cdh:
	di			;17cd	f3		.
	ld hl,05b00h		;17ce	21 00 5b	! . [
	ld b,008h		;17d1	06 08		. .
l17d3h:
	push bc			;17d3	c5		.
	call sub_17dch		;17d4	cd dc 17	. . .
	pop bc			;17d7	c1		.
	djnz l17d3h		;17d8	10 f9		. .
	jr l17b3h		;17da	18 d7		. .
sub_17dch:
	ld a,b			;17dc	78		x
	cp 003h			;17dd	fe 03		. .
	sbc a,a			;17df	9f		.
	and 002h		;17e0	e6 02		. .
	out (0fbh),a		;17e2	d3 fb		. .
	ld d,a			;17e4	57		W
l17e5h:
	call BREAK_KEY		;17e5	cd 09 20	. .  
	jr c,l17efh		;17e8	38 05		8 .
	call sub_17bah		;17ea	cd ba 17	. . .
	rst 8			;17ed	cf		.
	inc c			;17ee	0c		.
l17efh:
	in a,(0fbh)		;17ef	db fb		. .
	add a,a			;17f1	87		.
	ret m			;17f2	f8		.
	jr nc,l17e5h		;17f3	30 f0		0 .
	ld c,020h		;17f5	0e 20		.  
l17f7h:
	ld e,(hl)		;17f7	5e		^
	inc hl			;17f8	23		#
	ld b,008h		;17f9	06 08		. .
l17fbh:
	rl d			;17fb	cb 12		. .
	rl e			;17fd	cb 13		. .
	rr d			;17ff	cb 1a		. .
l1801h:
	in a,(0fbh)		;1801	db fb		. .
	rra			;1803	1f		.
	jr nc,l1801h		;1804	30 fb		0 .
	ld a,d			;1806	7a		z
	out (0fbh),a		;1807	d3 fb		. .
	djnz l17fbh		;1809	10 f0		. .
	dec c			;180b	0d		.
	jr nz,l17f7h		;180c	20 e9		  .
	ret			;180e	c9		.
l180fh:
	push af			;180f	f5		.
	push hl			;1810	e5		.
	sub 090h		;1811	d6 90		. .
	ld l,a			;1813	6f		o
	ld h,000h		;1814	26 00		& .
	push bc			;1816	c5		.
	ld bc,(05c7bh)		;1817	ed 4b 7b 5c	. K { \
	add hl,hl		;181b	29		)
	add hl,hl		;181c	29		)
	add hl,hl		;181d	29		)
	add hl,bc		;181e	09		.
	pop bc			;181f	c1		.
l1820h:
	ld (05dd7h),hl		;1820	22 d7 5d	" . ]
	pop hl			;1823	e1		.
	pop af			;1824	f1		.
	jp l1668h		;1825	c3 68 16	. h .
sub_1828h:
	ld c,00eh		;1828	0e 0e		. .
	call TSPICO_READ_DATA	;182a	cd 98 22	. . "
	and a			;182d	a7		.
	jp z,l0414h		;182e	ca 14 04	. . .
	dec a			;1831	3d		=
	jp nz,l0416h		;1832	c2 16 04	. . .
	call WAIT_PICO_READY	;1835	cd 54 1a	. T .
	jp c,l0414h		;1838	da 14 04	. . .
	ret			;183b	c9		.
	rst 38h			;183c	ff		.
	rst 38h			;183d	ff		.
	rst 38h			;183e	ff		.
	rst 38h			;183f	ff		.
BIOS_TABLE:
	jr l1856h		;1840	18 14		. .
	jr l1862h		;1842	18 1e		. .
	jr BIOS_G_VERS		;1844	18 0c		. .
BIOS_TX_A:
	jr l186dh		;1846	18 25		. %
BIOS_RX_A:
	jr l186ah		;1848	18 20		.  
sub_184ah:
	jr l184fh		;184a	18 03		. .
sub_184ch:
	jp BIOS_WF_NPH		;184c	c3 9e 23	. . #
l184fh:
	jp C_END_VEC		;184f	c3 1b 30	. . 0
BIOS_G_VERS:
	ld bc,l0021h		;1852	01 21 00	. ! .
	ret			;1855	c9		.
l1856h:
	push af			;1856	f5		.
	ld a,(05ddbh)		;1857	3a db 5d	: . ]
	and 00fh		;185a	e6 0f		. .
	ld b,000h		;185c	06 00		. .
	ld c,a			;185e	4f		O
	pop af			;185f	f1		.
	ret			;1860	c9		.
	xor a			;1861	af		.
l1862h:
	push af			;1862	f5		.
	and 00fh		;1863	e6 0f		. .
	ld (05ddbh),a		;1865	32 db 5d	2 . ]
	pop af			;1868	f1		.
	ret			;1869	c9		.
l186ah:
	jp TSPICO_READ_DATA	;186a	c3 98 22	. . "
l186dh:
	jp TSPICO_WRITE_DATA	;186d	c3 9d 22	. . "
	and a			;1870	a7		.
	ret			;1871	c9		.
l1872h:
	pop af			;1872	f1		.
	ld hl,l00e5h		;1873	21 e5 00	! . .
	jp l006bh		;1876	c3 6b 00	. k .
l1879h:
	push af			;1879	f5		.
	ld a,(05ddbh)		;187a	3a db 5d	: . ]
	and 002h		;187d	e6 02		. .
	jr z,l1872h		;187f	28 f1		( .
	pop af			;1881	f1		.
	ld hl,l00e5h		;1882	21 e5 00	! . .
	push hl			;1885	e5		.
	push af			;1886	f5		.
	di			;1887	f3		.
	ld l,a			;1888	6f		o
	and a			;1889	a7		.
	jr nz,l1890h		;188a	20 04		  .
	ld c,001h		;188c	0e 01		. .
	jr l189ah		;188e	18 0a		. .
l1890h:
	cp 0ffh			;1890	fe ff		. .
	jr nz,l1898h		;1892	20 04		  .
	ld c,003h		;1894	0e 03		. .
	jr l18d8h		;1896	18 40		. @
l1898h:
	ld c,009h		;1898	0e 09		. .
l189ah:
	call SYNC_WRITE		;189a	cd 00 23	. . #
	jp c,l192fh		;189d	da 2f 19	. / .
	push de			;18a0	d5		.
	ld a,(05c74h)		;18a1	3a 74 5c	: t \
	call sub_1963h		;18a4	cd 63 19	. c .
	ld a,(05dcfh)		;18a7	3a cf 5d	: . ]
	call sub_1963h		;18aa	cd 63 19	. c .
	ld de,(05dd1h)		;18ad	ed 5b d1 5d	. [ . ]
	call sub_1959h		;18b1	cd 59 19	. Y .
	push ix			;18b4	dd e5		. .
	pop de			;18b6	d1		.
	call sub_1959h		;18b7	cd 59 19	. Y .
	pop de			;18ba	d1		.
	call sub_1947h		;18bb	cd 47 19	. G .
	call TSPICO_WRITE_DATA	;18be	cd 9d 22	. . "
	jr c,l192fh		;18c1	38 6c		8 l
	inc c			;18c3	0c		.
	call TSPICO_READ_DATA	;18c4	cd 98 22	. . "
	jp c,l1c1fh		;18c7	da 1f 1c	. . .
	and a			;18ca	a7		.
	jp z,l1c1fh		;18cb	ca 1f 1c	. . .
	dec a			;18ce	3d		=
	jr nz,l192fh		;18cf	20 5e		  ^
	inc c			;18d1	0c		.
	call WAIT_PICO_READY	;18d2	cd 54 1a	. T .
	jp c,l1c1fh		;18d5	da 1f 1c	. . .
l18d8h:
	pop af			;18d8	f1		.
	ld h,a			;18d9	67		g
	call TSPICO_WRITE_DATA	;18da	cd 9d 22	. . "
	jr c,l1930h		;18dd	38 51		8 Q
	ld (05dcdh),de		;18df	ed 53 cd 5d	. S . ]
	ld de,(05dd1h)		;18e3	ed 5b d1 5d	. [ . ]
	call sub_1936h		;18e7	cd 36 19	. 6 .
	ld a,h			;18ea	7c		|
	and a			;18eb	a7		.
	call nz,sub_04e8h	;18ec	c4 e8 04	. . .
	ld de,(05dcdh)		;18ef	ed 5b cd 5d	. [ . ]
l18f3h:
	ld a,(ix+000h)		;18f3	dd 7e 00	. ~ .
	call TSPICO_WRITE_DATA	;18f6	cd 9d 22	. . "
	jr c,l1930h		;18f9	38 35		8 5
	xor h			;18fb	ac		.
	ld h,a			;18fc	67		g
	call STEP		;18fd	cd 39 23	. 9 #
	ld a,d			;1900	7a		z
	or e			;1901	b3		.
	jr nz,l18f3h		;1902	20 ef		  .
	ld a,h			;1904	7c		|
	call TSPICO_WRITE_DATA	;1905	cd 9d 22	. . "
	jr c,l1930h		;1908	38 26		8 &
	inc c			;190a	0c		.
	call WAIT_PICO_READY	;190b	cd 54 1a	. T .
	jp c,l1c20h		;190e	da 20 1c	.   .
	call TSPICO_READ_DATA	;1911	cd 98 22	. . "
	jp c,l1c20h		;1914	da 20 1c	.   .
	and a			;1917	a7		.
	jp z,l1c20h		;1918	ca 20 1c	.   .
	dec a			;191b	3d		=
	call nz,FN_CHAIN_HEAD	;191c	c4 6f 02	. o .
	ei			;191f	fb		.
	jr nz,l1930h		;1920	20 0e		  .
	scf			;1922	37		7
	ret			;1923	c9		.
sub_1924h:
	inc c			;1924	0c		.
	ld a,h			;1925	7c		|
	call TSPICO_WRITE_DATA	;1926	cd 9d 22	. . "
	jr c,l192fh		;1929	38 04		8 .
	dec c			;192b	0d		.
	ret			;192c	c9		.
l192dh:
	pop hl			;192d	e1		.
l192eh:
	pop hl			;192e	e1		.
l192fh:
	pop hl			;192f	e1		.
l1930h:
	pop hl			;1930	e1		.
	and a			;1931	a7		.
	ret z			;1932	c8		.
	jp STATUS_TO_REPORT	;1933	c3 f3 1b	. . .
sub_1936h:
	ld a,e			;1936	7b		{
	call TSPICO_WRITE_DATA	;1937	cd 9d 22	. . "
	jr c,l192fh		;193a	38 f3		8 .
	call sub_1956h		;193c	cd 56 19	. V .
	ld a,d			;193f	7a		z
	call TSPICO_WRITE_DATA	;1940	cd 9d 22	. . "
	jr c,l192fh		;1943	38 ea		8 .
	jr sub_1956h		;1945	18 0f		. .
sub_1947h:
	ld a,e			;1947	7b		{
	call TSPICO_WRITE_DATA	;1948	cd 9d 22	. . "
	jr c,l192eh		;194b	38 e1		8 .
	call sub_1956h		;194d	cd 56 19	. V .
	ld a,d			;1950	7a		z
sub_1951h:
	call TSPICO_WRITE_DATA	;1951	cd 9d 22	. . "
	jr c,l192eh		;1954	38 d8		8 .
sub_1956h:
	xor l			;1956	ad		.
	ld l,a			;1957	6f		o
	ret			;1958	c9		.
sub_1959h:
	ld a,e			;1959	7b		{
	call TSPICO_WRITE_DATA	;195a	cd 9d 22	. . "
	jr c,l192dh		;195d	38 ce		8 .
	call sub_1956h		;195f	cd 56 19	. V .
	ld a,d			;1962	7a		z
sub_1963h:
	call TSPICO_WRITE_DATA	;1963	cd 9d 22	. . "
	jr c,l192dh		;1966	38 c5		8 .
	jr sub_1956h		;1968	18 ec		. .
l196ah:
	jp l1930h		;196a	c3 30 19	. 0 .
l196dh:
	push af			;196d	f5		.
	ld a,(05ddbh)		;196e	3a db 5d	: . ]
	and 002h		;1971	e6 02		. .
	jp z,l1a4dh		;1973	ca 4d 1a	. M .
	pop af			;1976	f1		.
	ld hl,l00e5h		;1977	21 e5 00	! . .
	push hl			;197a	e5		.
	di			;197b	f3		.
	push de			;197c	d5		.
	push af			;197d	f5		.
	pop hl			;197e	e1		.
	res 6,l			;197f	cb b5		. .
	push hl			;1981	e5		.
	ld l,a			;1982	6f		o
	and a			;1983	a7		.
	jr nz,l198ah		;1984	20 04		  .
	ld c,005h		;1986	0e 05		. .
	jr l1994h		;1988	18 0a		. .
l198ah:
	cp 0ffh			;198a	fe ff		. .
	jr nz,l1992h		;198c	20 04		  .
	ld c,007h		;198e	0e 07		. .
	jr l1994h		;1990	18 02		. .
l1992h:
	ld c,00ah		;1992	0e 0a		. .
l1994h:
	pop af			;1994	f1		.
	ex af,af'		;1995	08		.
	ld a,l			;1996	7d		}
	ld h,a			;1997	67		g
	call SYNC_WRITE		;1998	cd 00 23	. . #
	jp c,l192fh		;199b	da 2f 19	. / .
	ld a,(05c74h)		;199e	3a 74 5c	: t \
	call sub_1951h		;19a1	cd 51 19	. Q .
	ld a,(05dcfh)		;19a4	3a cf 5d	: . ]
	call sub_1951h		;19a7	cd 51 19	. Q .
	ld de,(05dd1h)		;19aa	ed 5b d1 5d	. [ . ]
	call sub_1947h		;19ae	cd 47 19	. G .
	inc h			;19b1	24		$
	call z,sub_04e8h	;19b2	cc e8 04	. . .
	dec h			;19b5	25		%
	push ix			;19b6	dd e5		. .
	pop de			;19b8	d1		.
	call sub_1947h		;19b9	cd 47 19	. G .
	pop de			;19bc	d1		.
	call sub_1936h		;19bd	cd 36 19	. 6 .
	ld a,l			;19c0	7d		}
	call TSPICO_WRITE_DATA	;19c1	cd 9d 22	. . "
	jr c,l196ah		;19c4	38 a4		8 .
	inc c			;19c6	0c		.
	call TSPICO_READ_DATA	;19c7	cd 98 22	. . "
	jp c,l1c20h		;19ca	da 20 1c	.   .
	and a			;19cd	a7		.
	jp z,l1c20h		;19ce	ca 20 1c	.   .
	dec a			;19d1	3d		=
	jr nz,l1a35h		;19d2	20 61		  a
	call WAIT_PICO_READY	;19d4	cd 54 1a	. T .
	jp c,l1c20h		;19d7	da 20 1c	.   .
	call sub_1924h		;19da	cd 24 19	. $ .
l19ddh:
	call TSPICO_READ_DATA	;19dd	cd 98 22	. . "
	jr c,l196ah		;19e0	38 88		8 .
	ld l,a			;19e2	6f		o
	ex af,af'		;19e3	08		.
	jr nz,l1a20h		;19e4	20 3a		  :
	jr nc,l1a2dh		;19e6	30 45		0 E
	ld (ix+000h),l		;19e8	dd 75 00	. u .
	ex af,af'		;19eb	08		.
l19ech:
	ld a,h			;19ec	7c		|
	xor l			;19ed	ad		.
	ld h,a			;19ee	67		g
	call STEP		;19ef	cd 39 23	. 9 #
	ld a,d			;19f2	7a		z
	or e			;19f3	b3		.
	jr nz,l19ddh		;19f4	20 e7		  .
	call TSPICO_READ_DATA	;19f6	cd 98 22	. . "
	jp c,l196ah		;19f9	da 6a 19	. j .
	xor h			;19fc	ac		.
	and a			;19fd	a7		.
	jp nz,l0815h		;19fe	c2 15 08	. . .
	inc a			;1a01	3c		<
	call sub_1924h		;1a02	cd 24 19	. $ .
	call WAIT_PICO_READY	;1a05	cd 54 1a	. T .
	jp c,l1c20h		;1a08	da 20 1c	.   .
	call TSPICO_READ_DATA	;1a0b	cd 98 22	. . "
	jp c,l1c20h		;1a0e	da 20 1c	.   .
	and a			;1a11	a7		.
	jp z,l1c20h		;1a12	ca 20 1c	.   .
	dec a			;1a15	3d		=
	call nz,FN_CHAIN_HEAD	;1a16	c4 6f 02	. o .
	scf			;1a19	37		7
	ei			;1a1a	fb		.
	jr nz,l1a1eh		;1a1b	20 01		  .
	ret			;1a1d	c9		.
l1a1eh:
	ccf			;1a1e	3f		?
	ret			;1a1f	c9		.
l1a20h:
	rl b			;1a20	cb 10		. .
	xor l			;1a22	ad		.
	ret nz			;1a23	c0		.
	bit 0,b			;1a24	cb 40		. @
	jr z,l1a2ah		;1a26	28 02		( .
	cp a			;1a28	bf		.
	scf			;1a29	37		7
l1a2ah:
	ex af,af'		;1a2a	08		.
	jr l19ddh		;1a2b	18 b0		. .
l1a2dh:
	ex af,af'		;1a2d	08		.
	ld a,(ix+000h)		;1a2e	dd 7e 00	. ~ .
	xor l			;1a31	ad		.
	jr z,l19ech		;1a32	28 b8		( .
	ret			;1a34	c9		.
l1a35h:
	pop hl			;1a35	e1		.
	jp RPT_R_TAPE_ERROR	;1a36	c3 3e 1c	. > .
l1a39h:
	pop hl			;1a39	e1		.
l1a3ah:
	push af			;1a3a	f5		.
	ld a,(05ddbh)		;1a3b	3a db 5d	: . ]
	and 00fh		;1a3e	e6 0f		. .
	ld (05ddbh),a		;1a40	32 db 5d	2 . ]
	pop af			;1a43	f1		.
	pop de			;1a44	d1		.
l1a45h:
	pop de			;1a45	d1		.
	pop hl			;1a46	e1		.
	ld bc,l0010h+1		;1a47	01 11 00	. . .
	jp SAVE_ETC_BODY	;1a4a	c3 d5 01	. . .
l1a4dh:
	pop af			;1a4d	f1		.
	inc d			;1a4e	14		.
	ex af,af'		;1a4f	08		.
	dec d			;1a50	15		.
	jp l00ffh		;1a51	c3 ff 00	. . .
WAIT_PICO_READY:
	push af			;1a54	f5		.
	push bc			;1a55	c5		.
	ld b,0e2h		;1a56	06 e2		. .
l1a58h:
	call RD_STATUS		;1a58	cd 4f 23	. O #
	bit 6,a			;1a5b	cb 77		. w
	jr nz,WAIT_PICO_READY_OK	;1a5d	20 0f		  .
	djnz l1a58h		;1a5f	10 f7		. .
WAIT_PICO_READY_FAIL:
	ld a,040h		;1a61	3e 40		> @
	nop			;1a63	00		.
	nop			;1a64	00		.
	nop			;1a65	00		.
	nop			;1a66	00		.
	nop			;1a67	00		.
	pop bc			;1a68	c1		.
	pop af			;1a69	f1		.
	ld a,002h		;1a6a	3e 02		> .
	scf			;1a6c	37		7
	ret			;1a6d	c9		.
WAIT_PICO_READY_OK:
	pop bc			;1a6e	c1		.
	pop af			;1a6f	f1		.
	scf			;1a70	37		7
	ccf			;1a71	3f		?
	ret			;1a72	c9		.
SESSION_SETUP:
	push hl			;1a73	e5		.
	push de			;1a74	d5		.
	ld hl,(05c78h)		;1a75	2a 78 5c	* x \
l1a78h:
	inc hl			;1a78	23		#
	ld a,h			;1a79	7c		|
	or l			;1a7a	b5		.
	jr z,l1a78h		;1a7b	28 fb		( .
	ld (05dd1h),hl		;1a7d	22 d1 5d	" . ]
	ld hl,(05c65h)		;1a80	2a 65 5c	* e \
	dec hl			;1a83	2b		+
	ld b,(hl)		;1a84	46		F
	dec hl			;1a85	2b		+
	ld c,(hl)		;1a86	4e		N
	dec hl			;1a87	2b		+
	ld d,(hl)		;1a88	56		V
	dec hl			;1a89	2b		+
	ld e,(hl)		;1a8a	5e		^
	ld a,b			;1a8b	78		x
	and a			;1a8c	a7		.
	jr nz,l1a45h		;1a8d	20 b6		  .
	ld a,c			;1a8f	79		y
	cp 020h			;1a90	fe 20		.  
	jp nc,l1c2fh		;1a92	d2 2f 1c	. / .
	ld a,(05c74h)		;1a95	3a 74 5c	: t \
	and a			;1a98	a7		.
	jr z,l1aa0h		;1a99	28 05		( .
	cp 002h			;1a9b	fe 02		. .
	jp nc,l1a45h		;1a9d	d2 45 1a	. E .
l1aa0h:
	ld a,c			;1aa0	79		y
	cp 020h			;1aa1	fe 20		.  
	jr nc,l1a45h		;1aa3	30 a0		0 .
	and a			;1aa5	a7		.
	jr z,l1a45h		;1aa6	28 9d		( .
	cp 005h			;1aa8	fe 05		. .
	jr c,l1a45h		;1aaa	38 99		8 .
SESSION_NAMED:
	push de			;1aac	d5		.
	push de			;1aad	d5		.
	pop hl			;1aae	e1		.
	ld (05dd3h),hl		;1aaf	22 d3 5d	" . ]
	ld (05dd5h),bc		;1ab2	ed 43 d5 5d	. C . ]
	ld b,05fh		;1ab6	06 5f		. _
	ld a,b			;1ab8	78		x
	and (hl)		;1ab9	a6		.
	inc hl			;1aba	23		#
	cp 054h			;1abb	fe 54		. T
	jr z,l1adbh		;1abd	28 1c		( .
	cp 04eh			;1abf	fe 4e		. N
	jp nz,l1a3ah		;1ac1	c2 3a 1a	. : .
	ld a,b			;1ac4	78		x
	and (hl)		;1ac5	a6		.
	inc hl			;1ac6	23		#
	cp 045h			;1ac7	fe 45		. E
	jp nz,l1a3ah		;1ac9	c2 3a 1a	. : .
	ld a,b			;1acc	78		x
	and (hl)		;1acd	a6		.
	inc hl			;1ace	23		#
	cp 054h			;1acf	fe 54		. T
	jp nz,l1a3ah		;1ad1	c2 3a 1a	. : .
	ld a,(05ddbh)		;1ad4	3a db 5d	: . ]
	or 0c0h			;1ad7	f6 c0		. .
	jr l1af2h		;1ad9	18 17		. .
l1adbh:
	ld a,b			;1adb	78		x
	and (hl)		;1adc	a6		.
	inc hl			;1add	23		#
	cp 050h			;1ade	fe 50		. P
	jp nz,l1a3ah		;1ae0	c2 3a 1a	. : .
	ld a,b			;1ae3	78		x
	and (hl)		;1ae4	a6		.
	inc hl			;1ae5	23		#
	cp 049h			;1ae6	fe 49		. I
	jp nz,l1a3ah		;1ae8	c2 3a 1a	. : .
	ld a,(05ddbh)		;1aeb	3a db 5d	: . ]
	set 7,a			;1aee	cb ff		. .
	res 6,a			;1af0	cb b7		. .
l1af2h:
	ld (05ddbh),a		;1af2	32 db 5d	2 . ]
	ld a,03ah		;1af5	3e 3a		> :
	cp (hl)			;1af7	be		.
	jp nz,l1a3ah		;1af8	c2 3a 1a	. : .
	ld a,c			;1afb	79		y
	cp 006h			;1afc	fe 06		. .
	jp c,l1a3ah		;1afe	da 3a 1a	. : .
	ld a,(05c74h)		;1b01	3a 74 5c	: t \
	and a			;1b04	a7		.
	jp nz,l210eh		;1b05	c2 0e 21	. . !
	push hl			;1b08	e5		.
	xor a			;1b09	af		.
	ld h,a			;1b0a	67		g
	ld l,a			;1b0b	6f		o
	ld (05dd7h),hl		;1b0c	22 d7 5d	" . ]
	ld (05dd9h),hl		;1b0f	22 d9 5d	" . ]
	call sub_0303h		;1b12	cd 03 03	. . .
	cp 0afh			;1b15	fe af		. .
	jr z,l1b2ah		;1b17	28 11		( .
	call sub_1b6bh		;1b19	cd 6b 1b	. k .
	jr z,l1b48h		;1b1c	28 2a		( *
l1b1eh:
	jp l1a39h		;1b1e	c3 39 1a	. 9 .
sub_1b21h:
	call sub_02d7h		;1b21	cd d7 02	. . .
	call sub_03cah		;1b24	cd ca 03	. . .
	jp sub_037ch		;1b27	c3 7c 03	. | .
l1b2ah:
	call sub_1b21h		;1b2a	cd 21 1b	. ! .
	ld (05dd7h),bc		;1b2d	ed 43 d7 5d	. C . ]
	call sub_0303h		;1b31	cd 03 03	. . .
	cp 02ch			;1b34	fe 2c		. ,
	jp nz,l1c27h		;1b36	c2 27 1c	. ' .
	call sub_1b21h		;1b39	cd 21 1b	. ! .
	ld (05dd9h),bc		;1b3c	ed 43 d9 5d	. C . ]
	call sub_0303h		;1b40	cd 03 03	. . .
	call sub_1b6bh		;1b43	cd 6b 1b	. k .
	jr nz,l1b1eh		;1b46	20 d6		  .
l1b48h:
	bit 7,(iy+001h)		;1b48	fd cb 01 7e	. . . ~
	jp z,l1b71h		;1b4c	ca 71 1b	. q .
	pop hl			;1b4f	e1		.
	ld bc,(05dd5h)		;1b50	ed 4b d5 5d	. K . ]
	inc hl			;1b54	23		#
	ld b,05fh		;1b55	06 5f		. _
	ld a,b			;1b57	78		x
	and (hl)		;1b58	a6		.
	cp 054h			;1b59	fe 54		. T
	jp z,l208eh		;1b5b	ca 8e 20	. .  
	cp 053h			;1b5e	fe 53		. S
	jp z,l20c3h		;1b60	ca c3 20	. .  
	cp 050h			;1b63	fe 50		. P
	jp z,l2111h		;1b65	ca 11 21	. . !
	jp l210eh		;1b68	c3 0e 21	. . !
sub_1b6bh:
	cp 00dh			;1b6b	fe 0d		. .
	ret z			;1b6d	c8		.
	cp 03ah			;1b6e	fe 3a		. :
	ret			;1b70	c9		.
l1b71h:
	pop hl			;1b71	e1		.
l1b72h:
	pop de			;1b72	d1		.
	jp STATUS_OK		;1b73	c3 23 1c	. # .
	call TSPICO_WRITE_DATA	;1b76	cd 9d 22	. . "
	jp c,l1c20h		;1b79	da 20 1c	.   .
	jr l1b83h		;1b7c	18 05		. .
SEND_BYTE_CRC:
	call TSPICO_WRITE_DATA	;1b7e	cd 9d 22	. . "
	jr c,l1b86h		;1b81	38 03		8 .
l1b83h:
	xor d			;1b83	aa		.
	ld d,a			;1b84	57		W
	ret			;1b85	c9		.
l1b86h:
	pop hl			;1b86	e1		.
l1b87h:
	pop hl			;1b87	e1		.
l1b88h:
	pop hl			;1b88	e1		.
	pop hl			;1b89	e1		.
	jp RPT_R_TAPE_ERROR	;1b8a	c3 3e 1c	. > .
l1b8dh:
	push af			;1b8d	f5		.
	ld a,(05ddbh)		;1b8e	3a db 5d	: . ]
	res 7,a			;1b91	cb bf		. .
	res 6,a			;1b93	cb b7		. .
	ld (05ddbh),a		;1b95	32 db 5d	2 . ]
	pop af			;1b98	f1		.
	call sub_042fh		;1b99	cd 2f 04	. / .
	ld a,c			;1b9c	79		y
	or a			;1b9d	b7		.
	jr z,l1b88h		;1b9e	28 e8		( .
BUILD_PREHEADER_B:
	ld (05dcdh),bc		;1ba0	ed 43 cd 5d	. C . ]
	ld b,c			;1ba4	41		A
	ld c,00dh		;1ba5	0e 0d		. .
	ld a,042h		;1ba7	3e 42		> B
	ld d,a			;1ba9	57		W
	call SYNC_WRITE		;1baa	cd 00 23	. . #
	jr c,l1b87h		;1bad	38 d8		8 .
	ld a,(05c74h)		;1baf	3a 74 5c	: t \
	call SEND_BYTE_CRC	;1bb2	cd 7e 1b	. ~ .
	ld a,(05dcfh)		;1bb5	3a cf 5d	: . ]
	call SEND_BYTE_CRC	;1bb8	cd 7e 1b	. ~ .
	ld hl,(05dd7h)		;1bbb	2a d7 5d	* . ]
	ld a,l			;1bbe	7d		}
	call SEND_BYTE_CRC	;1bbf	cd 7e 1b	. ~ .
	ld a,h			;1bc2	7c		|
	call SEND_BYTE_CRC	;1bc3	cd 7e 1b	. ~ .
	ld hl,(05dd9h)		;1bc6	2a d9 5d	* . ]
	ld a,l			;1bc9	7d		}
	call SEND_BYTE_CRC	;1bca	cd 7e 1b	. ~ .
	ld a,h			;1bcd	7c		|
	call SEND_BYTE_CRC	;1bce	cd 7e 1b	. ~ .
	ld a,b			;1bd1	78		x
	call SEND_BYTE_CRC	;1bd2	cd 7e 1b	. ~ .
	ld a,(05dceh)		;1bd5	3a ce 5d	: . ]
	call SEND_BYTE_CRC	;1bd8	cd 7e 1b	. ~ .
	call SEND_BYTE_CRC	;1bdb	cd 7e 1b	. ~ .
	ld d,000h		;1bde	16 00		. .
	pop hl			;1be0	e1		.
	ld hl,(05dd3h)		;1be1	2a d3 5d	* . ]
	call SEND_DATA_BLOCK_D	;1be4	cd 3e 22	. > "
	jp c,l1bf1h		;1be7	da f1 1b	. . .
	and a			;1bea	a7		.
	jp z,STATUS_OK		;1beb	ca 23 1c	. # .
	push af			;1bee	f5		.
H_EXPT_STR:
	xor a			;1bef	af		.
	pop af			;1bf0	f1		.
l1bf1h:
	pop de			;1bf1	d1		.
l1bf2h:
	pop hl			;1bf2	e1		.
STATUS_TO_REPORT:
STATUS_REPORT:
	ei			;1bf3	fb		.
	dec a			;1bf4	3d		=
	jp z,RPT_R_TAPE_ERROR	;1bf5	ca 3e 1c	. > .
	dec a			;1bf8	3d		=
	jp z,RPT_F_BAD_FILENAME	;1bf9	ca 39 1c	. 9 .
	dec a			;1bfc	3d		=
	jp z,RPT_Q_PARAM_ERROR	;1bfd	ca 3c 1c	. < .
	dec a			;1c00	3d		=
	jp z,RPT_C_NONSENSE	;1c01	ca 35 1c	. 5 .
	dec a			;1c04	3d		=
	jr z,RPT_6_NUM_TOO_BIG	;1c05	28 0f		( .
	dec a			;1c07	3d		=
	jr z,RPT_8_END_OF_FILE	;1c08	28 0e		( .
	dec a			;1c0a	3d		=
	jr z,RPT_A_INVALID_ARG	;1c0b	28 0f		( .
	dec a			;1c0d	3d		=
	jr z,RPT_9_STOP		;1c0e	28 0a		( .
	dec a			;1c10	3d		=
	jr z,RPT_J_INVALID_IO	;1c11	28 0e		( .
	jp RPT_D_BREAK_CONT	;1c13	c3 f8 00	. . .
RPT_6_NUM_TOO_BIG:
	rst 8			;1c16	cf		.
	dec b			;1c17	05		.
RPT_8_END_OF_FILE:
	rst 8			;1c18	cf		.
	rlca			;1c19	07		.
RPT_9_STOP:
	rst 8			;1c1a	cf		.
	ex af,af'		;1c1b	08		.
RPT_A_INVALID_ARG:
	rst 8			;1c1c	cf		.
	add hl,bc		;1c1d	09		.
	pop hl			;1c1e	e1		.
l1c1fh:
	pop hl			;1c1f	e1		.
l1c20h:
	pop hl			;1c20	e1		.
RPT_J_INVALID_IO:
	rst 8			;1c21	cf		.
	ld (de),a		;1c22	12		.
STATUS_OK:
	pop de			;1c23	d1		.
	pop hl			;1c24	e1		.
	xor a			;1c25	af		.
l1c26h:
	ret			;1c26	c9		.
l1c27h:
	pop hl			;1c27	e1		.
	pop hl			;1c28	e1		.
	pop hl			;1c29	e1		.
	pop de			;1c2a	d1		.
	pop hl			;1c2b	e1		.
	jp RPT_C_NONSENSE	;1c2c	c3 35 1c	. 5 .
l1c2fh:
	bit 7,(iy+001h)		;1c2f	fd cb 01 7e	. . . ~
	jr z,STATUS_OK		;1c33	28 ee		( .
RPT_C_NONSENSE:
	ei			;1c35	fb		.
	jp l08d9h		;1c36	c3 d9 08	. . .
RPT_F_BAD_FILENAME:
	jp l0228h		;1c39	c3 28 02	. ( .
RPT_Q_PARAM_ERROR:
	rst 8			;1c3c	cf		.
	add hl,de		;1c3d	19		.
RPT_R_TAPE_ERROR:
	rst 8			;1c3e	cf		.
	ld a,(de)		;1c3f	1a		.
SEND_KEY:
	call WAIT_PICO_READY	;1c40	cd 54 1a	. T .
	jp c,l1b87h		;1c43	da 87 1b	. . .
	jp TSPICO_WRITE_DATA	;1c46	c3 9d 22	. . "
l1c49h:
	ld hl,l1c5dh		;1c49	21 5d 1c	! ] .
	ld de,05b00h		;1c4c	11 00 5b	. . [
	ld bc,l0029h		;1c4f	01 29 00	. ) .
	ldir			;1c52	ed b0		. .
	call 05b00h		;1c54	cd 00 5b	. . [
	ld hl,05eeah		;1c57	21 ea 5e	! . ^
	jp l1c86h		;1c5a	c3 86 1c	. . .
l1c5dh:
	xor a			;1c5d	af		.
	call 05b05h		;1c5e	cd 05 5b	. . [
	ret			;1c61	c9		.
	ld de,05b0bh		;1c62	11 0b 5b	. . [
	jp EX_PO_MSG		;1c65	c3 ed 03	. . .
	add a,b			;1c68	80		.
	dec c			;1c69	0d		.
	dec c			;1c6a	0d		.
	ld a,a			;1c6b	7f		.
	jr nz,l1ca0h		;1c6c	20 32		  2
	jr nc,$+52		;1c6e	30 32		0 2
	ld (hl),020h		;1c70	36 20		6  
	ld d,h			;1c72	54		T
	ld d,e			;1c73	53		S
	dec l			;1c74	2d		-
	ld d,b			;1c75	50		P
	ld l,c			;1c76	69		i
	ld h,e			;1c77	63		c
	ld l,a			;1c78	6f		o
	jr nz,l1ccdh		;1c79	20 52		  R
	ld c,a			;1c7b	4f		O
	ld c,l			;1c7c	4d		M
	jr nz,l1cf5h		;1c7d	20 76		  v
	ld (FDD_MOVE.cd+1),a	;1c7f	32 2e 31	2 . 1
	jr nz,l1ca4h		;1c82	20 20		   
	jr nz,l1c26h		;1c84	20 a0		  .
l1c86h:
	ld hl,05eeah		;1c86	21 ea 5e	! . ^
	ld (05cbch),hl		;1c89	22 bc 5c	" . \
	xor a			;1c8c	af		.
	ld (05cbeh),a		;1c8d	32 be 5c	2 . \
	ld (06315h),a		;1c90	32 15 63	2 . c
	ld a,0fdh		;1c93	3e fd		> .
	in a,(0feh)		;1c95	db fe		. .
	bit 2,a			;1c97	cb 57		. W
	jp nz,l08eah		;1c99	c2 ea 08	. . .
	xor a			;1c9c	af		.
	ld (hl),a		;1c9d	77		w
	inc hl			;1c9e	23		#
	ld (hl),a		;1c9f	77		w
l1ca0h:
	ld de,l0007h		;1ca0	11 07 00	. . .
	add hl,de		;1ca3	19		.
l1ca4h:
	ld (hl),a		;1ca4	77		w
	ld (05cc6h),a		;1ca5	32 c6 5c	2 . \
	call l0a3eh		;1ca8	cd 3e 0a	. > .
	jp l0918h		;1cab	c3 18 09	. . .
l1caeh:
	ld hl,l004fh		;1cae	21 4f 00	! O .
	ld de,06000h		;1cb1	11 00 60	. . `
	ld bc,l000bh		;1cb4	01 0b 00	. . .
	ldir			;1cb7	ed b0		. .
	jp 06000h		;1cb9	c3 00 60	. . `
l1cbch:
	push af			;1cbc	f5		.
	ld a,(05cc2h)		;1cbd	3a c2 5c	: . \
	and a			;1cc0	a7		.
	jr nz,l1cc7h		;1cc1	20 04		  .
	pop af			;1cc3	f1		.
	jp 06307h		;1cc4	c3 07 63	. . c
l1cc7h:
	pop af			;1cc7	f1		.
	jp 0fac7h		;1cc8	c3 c7 fa	. . .
	nop			;1ccb	00		.
	nop			;1ccc	00		.
l1ccdh:
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
l1cf5h:
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
	ld hl,(CH_OUT+1)	;1d18	2a 63 35	* c 5
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
	ld (l3a65h),a		;1d3c	32 65 3a	2 e :
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
	ld a,(l3acah)		;1f0b	3a ca 3a	: . :
	cp e			;1f0e	bb		.
l1f0fh:
	ld a,(l3656h)		;1f0f	3a 56 36	: V 6
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
	ld sp,l3193h		;1f1f	31 93 31	1 . 1
l1f22h:
	ld h,b			;1f22	60		`
H_FIND_INT2:
	ld sp,l30f9h		;1f23	31 f9 30	1 . 0
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
	ld hl,l2159h		;1f5d	21 59 21	! Y !
	ld d,l			;1f60	55		U
	ld hl,l201dh		;1f61	21 1d 20	! .  
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
	ld (0d067h),hl		;1fd8	22 67 d0	" g .
	ld h,l			;1fdb	65		e
	ld (hl),d		;1fdc	72		r
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
	adc a,(hl)		;1fee	8e		.
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
ENTRY_TABLE:
	jp BEEPER		;2000	c3 3f 20	. ?  
HALT_STUB_2003:
	jp HALT_STUB_2003	;2003	c3 03 20	. .  
HALT_STUB_2006:
	jp HALT_STUB_2006	;2006	c3 06 20	. .  
BREAK_KEY:
	ld a,07fh		;2009	3e 7f		> .
	in a,(0feh)		;200b	db fe		. .
	rra			;200d	1f		.
	ret c			;200e	d8		.
	bit 6,(iy+07dh)		;200f	fd cb 7d 76	. . } v
	jr z,l2017h		;2013	28 02		( .
	scf			;2015	37		7
	ret			;2016	c9		.
l2017h:
	ld a,0feh		;2017	3e fe		> .
	in a,(0feh)		;2019	db fe		. .
	rra			;201b	1f		.
	ret c			;201c	d8		.
l201dh:
	ret			;201d	c9		.
	ld a,020h		;201e	3e 20		>  
	out (00fh),a		;2020	d3 0f		. .
	xor a			;2022	af		.
	out (00fh),a		;2023	d3 0f		. .
	pop af			;2025	f1		.
	ret			;2026	c9		.
HALT_STUB_2027:
	jp HALT_STUB_2027	;2027	c3 27 20	. '  
HALT_STUB_202A:
	jp HALT_STUB_202A	;202a	c3 2a 20	. *  
HALT_STUB_202D:
	jp HALT_STUB_202D	;202d	c3 2d 20	. -  
HALT_STUB_2030:
	jp HALT_STUB_2030	;2030	c3 30 20	. 0  
HALT_STUB_2033:
	jp HALT_STUB_2033	;2033	c3 33 20	. 3  
HALT_STUB_2036:
	jp HALT_STUB_2036	;2036	c3 36 20	. 6  
HALT_STUB_2039:
	jp HALT_STUB_2039	;2039	c3 39 20	. 9  
HALT_STUB_203C:
	jp HALT_STUB_203C	;203c	c3 3c 20	. <  
BEEPER:
	di			;203f	f3		.
	ld a,l			;2040	7d		}
	srl l			;2041	cb 3d		. =
	srl l			;2043	cb 3d		. =
	cpl			;2045	2f		/
	and 003h		;2046	e6 03		. .
	ld c,a			;2048	4f		O
	ld b,000h		;2049	06 00		. .
	ld ix,l205bh		;204b	dd 21 5b 20	. ! [  
	add ix,bc		;204f	dd 09		. .
	ld a,(05c48h)		;2051	3a 48 5c	: H \
	and 038h		;2054	e6 38		. 8
	rrca			;2056	0f		.
	rrca			;2057	0f		.
	rrca			;2058	0f		.
	or 008h			;2059	f6 08		. .
l205bh:
	nop			;205b	00		.
	nop			;205c	00		.
	nop			;205d	00		.
	inc b			;205e	04		.
	inc c			;205f	0c		.
l2060h:
	dec c			;2060	0d		.
	jr nz,l2060h		;2061	20 fd		  .
	ld c,03fh		;2063	0e 3f		. ?
	dec b			;2065	05		.
	jp nz,l2060h		;2066	c2 60 20	. `  
	xor 010h		;2069	ee 10		. .
	out (0feh),a		;206b	d3 fe		. .
	ld b,h			;206d	44		D
	ld c,a			;206e	4f		O
	bit 4,a			;206f	cb 67		. g
	jr nz,l207ch		;2071	20 09		  .
	ld a,d			;2073	7a		z
	or e			;2074	b3		.
	jr z,l2080h		;2075	28 09		( .
	ld a,c			;2077	79		y
	ld c,l			;2078	4d		M
	dec de			;2079	1b		.
	jp (ix)			;207a	dd e9		. .
l207ch:
	ld c,l			;207c	4d		M
	inc c			;207d	0c		.
	jp (ix)			;207e	dd e9		. .
l2080h:
	ei			;2080	fb		.
	ret			;2081	c9		.
sub_2082h:
	dec hl			;2082	2b		+
	ld (hl),080h		;2083	36 80		6 .
	push ix			;2085	dd e5		. .
	exx			;2087	d9		.
	ld hl,00a35h		;2088	21 35 0a	! 5 .
	jp CALL_HOME		;208b	c3 dd 03	. . .
l208eh:
	inc hl			;208e	23		#
	ld a,b			;208f	78		x
	and (hl)		;2090	a6		.
	cp 041h			;2091	fe 41		. A
	jp nz,l2155h		;2093	c2 55 21	. U !
	inc hl			;2096	23		#
	ld a,b			;2097	78		x
	and (hl)		;2098	a6		.
	cp 050h			;2099	fe 50		. P
	jr nz,l210eh		;209b	20 71		  q
	inc hl			;209d	23		#
	ld a,b			;209e	78		x
	and (hl)		;209f	a6		.
	cp 045h			;20a0	fe 45		. E
	jr nz,l210eh		;20a2	20 6a		  j
	ld a,(05ddbh)		;20a4	3a db 5d	: . ]
	bit 7,a			;20a7	cb 7f		. .
	res 7,a			;20a9	cb bf		. .
	ld (05ddbh),a		;20ab	32 db 5d	2 . ]
	jr z,l210eh		;20ae	28 5e		( ^
	bit 6,a			;20b0	cb 77		. w
	res 6,a			;20b2	cb b7		. .
	ld (05ddbh),a		;20b4	32 db 5d	2 . ]
	jr nz,l210eh		;20b7	20 55		  U
	ld a,008h		;20b9	3e 08		> .
	cp c			;20bb	b9		.
	jr nz,l210eh		;20bc	20 50		  P
	jp TAPE_VEC		;20be	c3 1e 30	. . 0
	nop			;20c1	00		.
	nop			;20c2	00		.
l20c3h:
	inc hl			;20c3	23		#
	ld a,b			;20c4	78		x
	and (hl)		;20c5	a6		.
	cp 044h			;20c6	fe 44		. D
	jr nz,l210eh		;20c8	20 44		  D
	inc hl			;20ca	23		#
	ld a,b			;20cb	78		x
	and (hl)		;20cc	a6		.
	cp 043h			;20cd	fe 43		. C
	jr nz,l210eh		;20cf	20 3d		  =
	inc hl			;20d1	23		#
	ld a,b			;20d2	78		x
	and (hl)		;20d3	a6		.
	cp 041h			;20d4	fe 41		. A
	jr nz,l210eh		;20d6	20 36		  6
	inc hl			;20d8	23		#
	ld a,b			;20d9	78		x
	and (hl)		;20da	a6		.
	cp 052h			;20db	fe 52		. R
	jr nz,l210eh		;20dd	20 2f		  /
	inc hl			;20df	23		#
	ld a,b			;20e0	78		x
	and (hl)		;20e1	a6		.
	cp 044h			;20e2	fe 44		. D
	jr nz,l210eh		;20e4	20 28		  (
	ld a,(05ddbh)		;20e6	3a db 5d	: . ]
	bit 7,a			;20e9	cb 7f		. .
	res 7,a			;20eb	cb bf		. .
	ld (05ddbh),a		;20ed	32 db 5d	2 . ]
	jr z,l210eh		;20f0	28 1c		( .
	bit 6,a			;20f2	cb 77		. w
	res 6,a			;20f4	cb b7		. .
	ld (05ddbh),a		;20f6	32 db 5d	2 . ]
	jr nz,l210eh		;20f9	20 13		  .
	ld a,00ah		;20fb	3e 0a		> .
	cp c			;20fd	b9		.
	jr nz,l210eh		;20fe	20 0e		  .
	ld a,(05ddbh)		;2100	3a db 5d	: . ]
	or 002h			;2103	f6 02		. .
MODE_SET_OK:
	call l1862h		;2105	cd 62 18	. b .
	call sub_042fh		;2108	cd 2f 04	. / .
	jp l1b72h		;210b	c3 72 1b	. r .
l210eh:
	jp l1b8dh		;210e	c3 8d 1b	. . .
l2111h:
	inc hl			;2111	23		#
	ld a,b			;2112	78		x
	and (hl)		;2113	a6		.
	cp 049h			;2114	fe 49		. I
	jr nz,l210eh		;2116	20 f6		  .
	inc hl			;2118	23		#
	ld a,b			;2119	78		x
	and (hl)		;211a	a6		.
	cp 043h			;211b	fe 43		. C
	jr nz,l210eh		;211d	20 ef		  .
	inc hl			;211f	23		#
	ld a,b			;2120	78		x
	and (hl)		;2121	a6		.
	cp 04fh			;2122	fe 4f		. O
	jr nz,l210eh		;2124	20 e8		  .
	inc hl			;2126	23		#
	ld a,b			;2127	78		x
	and (hl)		;2128	a6		.
	cp 050h			;2129	fe 50		. P
	jr nz,l210eh		;212b	20 e1		  .
	inc hl			;212d	23		#
	ld a,b			;212e	78		x
	and (hl)		;212f	a6		.
	cp 054h			;2130	fe 54		. T
	jr nz,l210eh		;2132	20 da		  .
	ld a,(05ddbh)		;2134	3a db 5d	: . ]
	bit 7,a			;2137	cb 7f		. .
	res 7,a			;2139	cb bf		. .
	ld (05ddbh),a		;213b	32 db 5d	2 . ]
	jr z,l210eh		;213e	28 ce		( .
	bit 6,a			;2140	cb 77		. w
	res 6,a			;2142	cb b7		. .
	ld (05ddbh),a		;2144	32 db 5d	2 . ]
	jr nz,l210eh		;2147	20 c5		  .
	ld a,00ah		;2149	3e 0a		> .
	cp c			;214b	b9		.
	jr nz,l210eh		;214c	20 c0		  .
	ld a,(05ddbh)		;214e	3a db 5d	: . ]
	set 0,a			;2151	cb c7		. .
	jr MODE_SET_OK		;2153	18 b0		. .
l2155h:
	cp 053h			;2155	fe 53		. S
	jr nz,l210eh		;2157	20 b5		  .
l2159h:
	inc hl			;2159	23		#
	ld a,(hl)		;215a	7e		~
	cp 032h			;215b	fe 32		. 2
	jr nz,l210eh		;215d	20 af		  .
	inc hl			;215f	23		#
	ld a,(hl)		;2160	7e		~
	cp 030h			;2161	fe 30		. 0
	jr nz,l210eh		;2163	20 a9		  .
	inc hl			;2165	23		#
	ld a,(hl)		;2166	7e		~
	cp 034h			;2167	fe 34		. 4
	jr nz,l210eh		;2169	20 a3		  .
	inc hl			;216b	23		#
	ld a,(hl)		;216c	7e		~
	cp 030h			;216d	fe 30		. 0
	jr nz,l210eh		;216f	20 9d		  .
	ld a,(05ddbh)		;2171	3a db 5d	: . ]
	bit 7,a			;2174	cb 7f		. .
	res 7,a			;2176	cb bf		. .
	ld (05ddbh),a		;2178	32 db 5d	2 . ]
	jr z,l210eh		;217b	28 91		( .
	bit 6,a			;217d	cb 77		. w
	res 6,a			;217f	cb b7		. .
	ld (05ddbh),a		;2181	32 db 5d	2 . ]
	jr nz,l210eh		;2184	20 88		  .
	ld a,00ah		;2186	3e 0a		> .
	cp c			;2188	b9		.
	jp nz,l210eh		;2189	c2 0e 21	. . !
	ld a,(05ddbh)		;218c	3a db 5d	: . ]
	res 0,a			;218f	cb 87		. .
	jp MODE_SET_OK		;2191	c3 05 21	. . !
FN_CHAIN_C1:
	cp 081h			;2194	fe 81		. .
	jr nz,l21a4h		;2196	20 0c		  .
FN_82_PRINT_STR_KEY:
	call READ_STATUS_BYTE	;2198	cd b9 02	. . .
	call OPEN_MAIN_SCREEN	;219b	cd f1 04	. . .
	call PRINT_STRING_FROM_PICO	;219e	cd 5f 04	. _ .
	jp l21c1h		;21a1	c3 c1 21	. . !
l21a4h:
	cp 082h			;21a4	fe 82		. .
	jr nz,l21bah		;21a6	20 12		  .
FN_83_PRINT_CHAR:
	call READ_STATUS_BYTE	;21a8	cd b9 02	. . .
	push af			;21ab	f5		.
	call sub_21b1h		;21ac	cd b1 21	. . !
	pop af			;21af	f1		.
	ret			;21b0	c9		.
sub_21b1h:
	call OPEN_MAIN_SCREEN	;21b1	cd f1 04	. . .
	call TSPICO_READ_DATA	;21b4	cd 98 22	. . "
	jp sub_05fah		;21b7	c3 fa 05	. . .
l21bah:
	cp 083h			;21ba	fe 83		. .
	jr nz,l21c7h		;21bc	20 09		  .
FN_84_RETURN_KEY:
	call READ_STATUS_BYTE	;21be	cd b9 02	. . .
l21c1h:
	push af			;21c1	f5		.
	call GET_KEY_AND_SEND	;21c2	cd 71 04	. q .
	pop af			;21c5	f1		.
	ret			;21c6	c9		.
l21c7h:
	cp 084h			;21c7	fe 84		. .
	jr nz,l21dfh		;21c9	20 14		  .
FN_85_GET_STATUS:
	call READ_STATUS_BYTE	;21cb	cd b9 02	. . .
	push af			;21ce	f5		.
	push hl			;21cf	e5		.
	call GET_STATUS_BIT_0	;21d0	cd 5e 02	. ^ .
	ld l,a			;21d3	6f		o
	call GET_STATUS_BIT_1	;21d4	cd 6a 02	. j .
	add a,a			;21d7	87		.
	or l			;21d8	b5		.
	call TSPICO_WRITE_DATA	;21d9	cd 9d 22	. . "
	pop hl			;21dc	e1		.
	pop af			;21dd	f1		.
	ret			;21de	c9		.
l21dfh:
	cp 085h			;21df	fe 85		. .
	jr nz,l21fdh		;21e1	20 1a		  .
FN_86_YN_PROMPT:
	call READ_STATUS_AND_OPEN	;21e3	cd c3 01	. . .
LOOP_BODY:
	push af			;21e6	f5		.
YN_LOOP:
	call PRINT_STRING_FROM_PICO	;21e7	cd 5f 04	. _ .
	jp c,LOOP_EXIT_ERR	;21ea	da 13 08	. . .
	call GET_KEY_AND_SEND	;21ed	cd 71 04	. q .
	and 05fh		;21f0	e6 5f		. _
	cp 04eh			;21f2	fe 4e		. N
	jp nz,YN_LOOP_GUARD	;21f4	c2 a1 22	. . "
	jp LOOP_EXIT_OK		;21f7	c3 10 08	. . .
l21fah:
	pop af			;21fa	f1		.
	scf			;21fb	37		7
	ret			;21fc	c9		.
l21fdh:
	cp 086h			;21fd	fe 86		. .
	jr nz,l2213h		;21ff	20 12		  .
FN_87_PRINT_N_CHARS:
	call READ_STATUS_BYTE	;2201	cd b9 02	. . .
	push af			;2204	f5		.
	call sub_220ah		;2205	cd 0a 22	. . "
	pop af			;2208	f1		.
	ret			;2209	c9		.
sub_220ah:
	push ix			;220a	dd e5		. .
	exx			;220c	d9		.
	ld hl,008a6h		;220d	21 a6 08	! . .
	jp CALL_HOME		;2210	c3 dd 03	. . .
l2213h:
	cp 087h			;2213	fe 87		. .
	jp z,LOWER_VEC		;2215	ca 06 30	. . 0
	ret			;2218	c9		.
	push af			;2219	f5		.
	call BEEPER		;221a	cd 3f 20	. ?  
	pop af			;221d	f1		.
	ret			;221e	c9		.
sub_221fh:
	call sub_081dh		;221f	cd 1d 08	. . .
	call sub_096ch		;2222	cd 6c 09	. l .
	xor a			;2225	af		.
	ld (05cbeh),a		;2226	32 be 5c	2 . \
	ld (06315h),a		;2229	32 15 63	2 . c
	ret			;222c	c9		.
	rrca			;222d	0f		.
	ld a,080h		;222e	3e 80		> .
	ld (05ef6h),a		;2230	32 f6 5e	2 . ^
	ret			;2233	c9		.
	rrca			;2234	0f		.
	xor a			;2235	af		.
	out (00fh),a		;2236	d3 0f		. .
	ret			;2238	c9		.
	ld a,001h		;2239	3e 01		> .
	jp l192fh		;223b	c3 2f 19	. / .
SEND_DATA_BLOCK_D:
	call TSPICO_READ_DATA	;223e	cd 98 22	. . "
	jr c,ERR_9		;2241	38 51		8 Q
	and a			;2243	a7		.
	jr z,ERR_9		;2244	28 4e		( N
	dec a			;2246	3d		=
	call WAIT_PICO_READY	;2247	cd 54 1a	. T .
	jr c,ERR_9		;224a	38 48		8 H
	ret nz			;224c	c0		.
	ld a,044h		;224d	3e 44		> D
	ld d,a			;224f	57		W
	call TSPICO_WRITE_DATA	;2250	cd 9d 22	. . "
	jr c,ERR_9		;2253	38 3f		8 ?
	ld a,(05dcdh)		;2255	3a cd 5d	: . ]
	call SEND_BYTE_CRC	;2258	cd 7e 1b	. ~ .
	ld a,(05dceh)		;225b	3a ce 5d	: . ]
	call SEND_BYTE_CRC	;225e	cd 7e 1b	. ~ .
l2261h:
	ld a,(hl)		;2261	7e		~
	call SEND_BYTE_CRC	;2262	cd 7e 1b	. ~ .
	inc hl			;2265	23		#
	push hl			;2266	e5		.
	ld hl,(05dcdh)		;2267	2a cd 5d	* . ]
	dec hl			;226a	2b		+
	ld (05dcdh),hl		;226b	22 cd 5d	" . ]
	ld a,h			;226e	7c		|
	or l			;226f	b5		.
	pop hl			;2270	e1		.
	jr nz,l2261h		;2271	20 ee		  .
	ld a,d			;2273	7a		z
PICO_TRANSACT:
	call TSPICO_WRITE_DATA	;2274	cd 9d 22	. . "
	jr c,ERR_9		;2277	38 1b		8 .
	call WAIT_PICO_READY	;2279	cd 54 1a	. T .
	jp c,ERR_9		;227c	da 94 22	. . "
C_END_TAIL:
	ld c,00eh		;227f	0e 0e		. .
	call TSPICO_READ_DATA	;2281	cd 98 22	. . "
	jr c,ERR_9		;2284	38 0e		8 .
	and a			;2286	a7		.
	jp z,ERR_9		;2287	ca 94 22	. . "
	dec a			;228a	3d		=
	ret z			;228b	c8		.
	call FN_CHAIN_HEAD	;228c	cd 6f 02	. o .
	and a			;228f	a7		.
	jr nz,l2296h		;2290	20 04		  .
	and a			;2292	a7		.
	ret			;2293	c9		.
ERR_9:
	ld a,009h		;2294	3e 09		> .
l2296h:
	scf			;2296	37		7
	ret			;2297	c9		.
TSPICO_READ_DATA:
	in a,(00eh)		;2298	db 0e		. .
	and a			;229a	a7		.
	ret			;229b	c9		.
	ret			;229c	c9		.
TSPICO_WRITE_DATA:
TSPICO_WRITE:
	out (00eh),a		;229d	d3 0e		. .
	and a			;229f	a7		.
	ret			;22a0	c9		.
YN_LOOP_GUARD:
	call WAIT_PICO_READY	;22a1	cd 54 1a	. T .
	jr c,l22a9h		;22a4	38 03		8 .
	jp YN_LOOP		;22a6	c3 e7 21	. . !
l22a9h:
	pop af			;22a9	f1		.
	ld a,009h		;22aa	3e 09		> .
	scf			;22ac	37		7
	ret			;22ad	c9		.
sub_22aeh:
	set 5,(iy+002h)		;22ae	fd cb 02 ee	. . . .
	scf			;22b2	37		7
	push af			;22b3	f5		.
	push bc			;22b4	c5		.
	push de			;22b5	d5		.
	ld bc,09c40h		;22b6	01 40 9c	. @ .
l22b9h:
	dec bc			;22b9	0b		.
	ld a,c			;22ba	79		y
	or b			;22bb	b0		.
	jr nz,l22b9h		;22bc	20 fb		  .
l22beh:
	xor a			;22be	af		.
	in a,(0feh)		;22bf	db fe		. .
	and 01fh		;22c1	e6 1f		. .
	cp 01fh			;22c3	fe 1f		. .
	jr z,l22beh		;22c5	28 f7		( .
	ld b,00ch		;22c7	06 0c		. .
l22c9h:
	halt			;22c9	76		v
	djnz l22c9h		;22ca	10 fd		. .
	call sub_22f0h		;22cc	cd f0 22	. . "
	jp c,l08beh		;22cf	da be 08	. . .
	call sub_22e7h		;22d2	cd e7 22	. . "
	pop de			;22d5	d1		.
	pop bc			;22d6	c1		.
	pop af			;22d7	f1		.
	pop hl			;22d8	e1		.
	ex (sp),hl		;22d9	e3		.
	ld a,(05c48h)		;22da	3a 48 5c	: H \
	and 038h		;22dd	e6 38		. 8
	rrca			;22df	0f		.
	rrca			;22e0	0f		.
	rrca			;22e1	0f		.
	and a			;22e2	a7		.
	out (0feh),a		;22e3	d3 fe		. .
	ei			;22e5	fb		.
	ret			;22e6	c9		.
sub_22e7h:
	push ix			;22e7	dd e5		. .
	exx			;22e9	d9		.
	ld hl,008a9h		;22ea	21 a9 08	! . .
	jp CALL_HOME		;22ed	c3 dd 03	. . .
sub_22f0h:
	bit 6,(iy+07dh)		;22f0	fd cb 7d 76	. . } v
	jr z,l22f8h		;22f4	28 02		( .
	scf			;22f6	37		7
	ret			;22f7	c9		.
l22f8h:
	ld a,07fh		;22f8	3e 7f		> .
	in a,(0feh)		;22fa	db fe		. .
	rra			;22fc	1f		.
	ret			;22fd	c9		.
	rst 38h			;22fe	ff		.
	rst 38h			;22ff	ff		.
SYNC_WRITE:
	push af			;2300	f5		.
	push bc			;2301	c5		.
	ld a,003h		;2302	3e 03		> .
	out (00fh),a		;2304	d3 0f		. .
	call SYNC_WAIT		;2306	cd 0e 23	. . #
	pop bc			;2309	c1		.
	pop af			;230a	f1		.
	jp TSPICO_WRITE_DATA	;230b	c3 9d 22	. . "
SYNC_WAIT:
	ld bc,l0000h		;230e	01 00 00	. . .
SYNC_WAIT.poll:
	in a,(00fh)		;2311	db 0f		. .
	and 048h		;2313	e6 48		. H
	cp 048h			;2315	fe 48		. H
	ret z			;2317	c8		.
	dec bc			;2318	0b		.
	ld a,b			;2319	78		x
	or c			;231a	b1		.
	jr nz,SYNC_WAIT.poll	;231b	20 f4		  .
	ret			;231d	c9		.
BRK_ABORT:
	ld a,003h		;231e	3e 03		> .
	out (00fh),a		;2320	d3 0f		. .
	call SYNC_WAIT		;2322	cd 0e 23	. . #
	rst 8			;2325	cf		.
	inc c			;2326	0c		.
BRK_TEST:
	bit 6,(iy+07dh)		;2327	fd cb 7d 76	. . } v
	scf			;232b	37		7
	ret nz			;232c	c0		.
	ld a,07fh		;232d	3e 7f		> .
	in a,(0feh)		;232f	db fe		. .
	rra			;2331	1f		.
	ret c			;2332	d8		.
	ld a,0feh		;2333	3e fe		> .
	in a,(0feh)		;2335	db fe		. .
	rra			;2337	1f		.
	ret			;2338	c9		.
STEP:
	inc ix			;2339	dd 23		. #
	dec de			;233b	1b		.
	ld a,e			;233c	7b		{
	or a			;233d	b7		.
	ret nz			;233e	c0		.
	call BRK_TEST		;233f	cd 27 23	. ' #
	ret c			;2342	d8		.
	jp BRK_ABORT		;2343	c3 1e 23	. . #
KEYWAIT:
	call BRK_TEST		;2346	cd 27 23	. ' #
	jp nc,BRK_ABORT		;2349	d2 1e 23	. . #
	jp POLL_KEYPRESS	;234c	c3 46 05	. F .
RD_STATUS:
	call READ_STATUS	;234f	cd 55 06	. U .
	bit 6,a			;2352	cb 77		. w
	ret z			;2354	c8		.
	bit 2,a			;2355	cb 57		. W
	ret nz			;2357	c0		.
	rst 8			;2358	cf		.
	inc e			;2359	1c		.
EX_REPORT_MSG:
	cp 01dh			;235a	fe 1d		. .
	jr z,EX_REPORT_MSG.pico	;235c	28 08		( .
	ld de,HOME_MSG_TABLE	;235e	11 65 0f	. e .
	call EX_PO_MSG		;2361	cd ed 03	. . .
	jr EX_REPORT_MSG.sep	;2364	18 10		. .
EX_REPORT_MSG.pico:
	ld hl,MSG_PICO_RESET	;2366	21 86 23	! . #
EX_REPORT_MSG.chr:
	ld a,(hl)		;2369	7e		~
	and 07fh		;236a	e6 7f		. .
	push hl			;236c	e5		.
	call EX_HOME_PRINT	;236d	cd 7d 23	. } #
	pop hl			;2370	e1		.
	bit 7,(hl)		;2371	cb 7e		. ~
	inc hl			;2373	23		#
	jr z,EX_REPORT_MSG.chr	;2374	28 f3		( .
EX_REPORT_MSG.sep:
	xor a			;2376	af		.
	ld de,HOME_MSG_SEP	;2377	11 15 11	. . .
	jp EX_PO_MSG		;237a	c3 ed 03	. . .
EX_HOME_PRINT:
	push ix			;237d	dd e5		. .
	exx			;237f	d9		.
	ld hl,l0010h		;2380	21 10 00	! . .
	jp CALL_HOME		;2383	c3 dd 03	. . .
MSG_PICO_RESET:
	ld d,h			;2386	54		T
	ld d,e			;2387	53		S
	dec l			;2388	2d		-
	ld d,b			;2389	50		P
	ld l,c			;238a	69		i
	ld h,e			;238b	63		c
	ld l,a			;238c	6f		o
	jr nz,l2401h		;238d	20 72		  r
	ld h,l			;238f	65		e
	ld (hl),e		;2390	73		s
	ld h,l			;2391	65		e
	ld (hl),h		;2392	74		t
	inc l			;2393	2c		,
	jr nz,l240ah		;2394	20 74		  t
	ld (hl),d		;2396	72		r
	ld a,c			;2397	79		y
	jr nz,l23fbh		;2398	20 61		  a
	ld h,a			;239a	67		g
	ld h,c			;239b	61		a
	ld l,c			;239c	69		i
	xor 0f5h		;239d	ee f5		. .
	push bc			;239f	c5		.
	ld b,0e2h		;23a0	06 e2		. .
BIOS_WF_NPH.poll:
	call CHECK_BREAK	;23a2	cd 9f 06	. . .
	jr nc,BIOS_WF_NPH.brk	;23a5	30 17		0 .
	in a,(00fh)		;23a7	db 0f		. .
	bit 6,a			;23a9	cb 77		. w
	jr nz,BIOS_WF_NPH.ready	;23ab	20 06		  .
	djnz BIOS_WF_NPH.poll	;23ad	10 f3		. .
	ld c,002h		;23af	0e 02		. .
	jr BIOS_WF_NPH.fail	;23b1	18 14		. .
BIOS_WF_NPH.ready:
	bit 2,a			;23b3	cb 57		. W
	ld c,01ch		;23b5	0e 1c		. .
	jr z,BIOS_WF_NPH.fail	;23b7	28 0e		( .
	pop bc			;23b9	c1		.
	pop af			;23ba	f1		.
	scf			;23bb	37		7
	ccf			;23bc	3f		?
	ret			;23bd	c9		.
BIOS_WF_NPH.brk:
	ld a,003h		;23be	3e 03		> .
	out (00fh),a		;23c0	d3 0f		. .
	call SYNC_WAIT		;23c2	cd 0e 23	. . #
	ld c,00ch		;23c5	0e 0c		. .
BIOS_WF_NPH.fail:
	ld a,c			;23c7	79		y
	pop bc			;23c8	c1		.
	inc sp			;23c9	33		3
	inc sp			;23ca	33		3
	scf			;23cb	37		7
	ret			;23cc	c9		.
BIOS_C_END:
	call BIOS_WF_NPH	;23cd	cd 9e 23	. . #
	ret c			;23d0	d8		.
	jp C_END_TAIL		;23d1	c3 7f 22	. . "
NEW_CODE_END:
	rst 38h			;23d4	ff		.
	rst 38h			;23d5	ff		.
	rst 38h			;23d6	ff		.
	rst 38h			;23d7	ff		.
	rst 38h			;23d8	ff		.
	rst 38h			;23d9	ff		.
	rst 38h			;23da	ff		.
	rst 38h			;23db	ff		.
	rst 38h			;23dc	ff		.
	rst 38h			;23dd	ff		.
	rst 38h			;23de	ff		.
	rst 38h			;23df	ff		.
	rst 38h			;23e0	ff		.
	rst 38h			;23e1	ff		.
	rst 38h			;23e2	ff		.
	rst 38h			;23e3	ff		.
	rst 38h			;23e4	ff		.
	rst 38h			;23e5	ff		.
	rst 38h			;23e6	ff		.
	rst 38h			;23e7	ff		.
	rst 38h			;23e8	ff		.
	rst 38h			;23e9	ff		.
	rst 38h			;23ea	ff		.
	rst 38h			;23eb	ff		.
	rst 38h			;23ec	ff		.
	rst 38h			;23ed	ff		.
	rst 38h			;23ee	ff		.
	rst 38h			;23ef	ff		.
	rst 38h			;23f0	ff		.
	rst 38h			;23f1	ff		.
	rst 38h			;23f2	ff		.
	rst 38h			;23f3	ff		.
	rst 38h			;23f4	ff		.
	rst 38h			;23f5	ff		.
	rst 38h			;23f6	ff		.
	rst 38h			;23f7	ff		.
	rst 38h			;23f8	ff		.
	rst 38h			;23f9	ff		.
	rst 38h			;23fa	ff		.
l23fbh:
	rst 38h			;23fb	ff		.
	rst 38h			;23fc	ff		.
	rst 38h			;23fd	ff		.
	rst 38h			;23fe	ff		.
	rst 38h			;23ff	ff		.
	rst 38h			;2400	ff		.
l2401h:
	rst 38h			;2401	ff		.
	rst 38h			;2402	ff		.
	rst 38h			;2403	ff		.
	rst 38h			;2404	ff		.
	rst 38h			;2405	ff		.
	rst 38h			;2406	ff		.
	rst 38h			;2407	ff		.
	rst 38h			;2408	ff		.
	rst 38h			;2409	ff		.
l240ah:
	rst 38h			;240a	ff		.
	rst 38h			;240b	ff		.
	rst 38h			;240c	ff		.
	rst 38h			;240d	ff		.
	rst 38h			;240e	ff		.
	rst 38h			;240f	ff		.
	rst 38h			;2410	ff		.
	rst 38h			;2411	ff		.
	rst 38h			;2412	ff		.
	rst 38h			;2413	ff		.
	rst 38h			;2414	ff		.
	rst 38h			;2415	ff		.
	rst 38h			;2416	ff		.
	rst 38h			;2417	ff		.
	rst 38h			;2418	ff		.
	rst 38h			;2419	ff		.
	rst 38h			;241a	ff		.
	rst 38h			;241b	ff		.
	rst 38h			;241c	ff		.
	rst 38h			;241d	ff		.
	rst 38h			;241e	ff		.
	rst 38h			;241f	ff		.
	rst 38h			;2420	ff		.
	rst 38h			;2421	ff		.
	rst 38h			;2422	ff		.
	rst 38h			;2423	ff		.
	rst 38h			;2424	ff		.
	rst 38h			;2425	ff		.
	rst 38h			;2426	ff		.
	rst 38h			;2427	ff		.
	rst 38h			;2428	ff		.
	rst 38h			;2429	ff		.
	rst 38h			;242a	ff		.
	rst 38h			;242b	ff		.
	rst 38h			;242c	ff		.
	rst 38h			;242d	ff		.
	rst 38h			;242e	ff		.
	rst 38h			;242f	ff		.
	rst 38h			;2430	ff		.
	rst 38h			;2431	ff		.
	rst 38h			;2432	ff		.
	rst 38h			;2433	ff		.
	rst 38h			;2434	ff		.
	rst 38h			;2435	ff		.
	rst 38h			;2436	ff		.
	rst 38h			;2437	ff		.
	rst 38h			;2438	ff		.
	rst 38h			;2439	ff		.
	rst 38h			;243a	ff		.
	rst 38h			;243b	ff		.
	rst 38h			;243c	ff		.
	rst 38h			;243d	ff		.
	rst 38h			;243e	ff		.
	rst 38h			;243f	ff		.
	rst 38h			;2440	ff		.
	rst 38h			;2441	ff		.
	rst 38h			;2442	ff		.
	rst 38h			;2443	ff		.
	rst 38h			;2444	ff		.
	rst 38h			;2445	ff		.
	rst 38h			;2446	ff		.
	rst 38h			;2447	ff		.
	rst 38h			;2448	ff		.
	rst 38h			;2449	ff		.
	rst 38h			;244a	ff		.
	rst 38h			;244b	ff		.
	rst 38h			;244c	ff		.
	rst 38h			;244d	ff		.
	rst 38h			;244e	ff		.
	rst 38h			;244f	ff		.
	rst 38h			;2450	ff		.
	rst 38h			;2451	ff		.
	rst 38h			;2452	ff		.
	rst 38h			;2453	ff		.
	rst 38h			;2454	ff		.
	rst 38h			;2455	ff		.
	rst 38h			;2456	ff		.
	rst 38h			;2457	ff		.
	rst 38h			;2458	ff		.
	rst 38h			;2459	ff		.
	rst 38h			;245a	ff		.
	rst 38h			;245b	ff		.
	rst 38h			;245c	ff		.
	rst 38h			;245d	ff		.
	rst 38h			;245e	ff		.
	rst 38h			;245f	ff		.
	rst 38h			;2460	ff		.
	rst 38h			;2461	ff		.
	rst 38h			;2462	ff		.
	rst 38h			;2463	ff		.
	rst 38h			;2464	ff		.
	rst 38h			;2465	ff		.
	rst 38h			;2466	ff		.
	rst 38h			;2467	ff		.
	rst 38h			;2468	ff		.
	rst 38h			;2469	ff		.
	rst 38h			;246a	ff		.
	rst 38h			;246b	ff		.
	rst 38h			;246c	ff		.
	rst 38h			;246d	ff		.
	rst 38h			;246e	ff		.
	rst 38h			;246f	ff		.
	rst 38h			;2470	ff		.
	rst 38h			;2471	ff		.
	rst 38h			;2472	ff		.
	rst 38h			;2473	ff		.
	rst 38h			;2474	ff		.
	rst 38h			;2475	ff		.
	rst 38h			;2476	ff		.
	rst 38h			;2477	ff		.
	rst 38h			;2478	ff		.
	rst 38h			;2479	ff		.
	rst 38h			;247a	ff		.
	rst 38h			;247b	ff		.
	rst 38h			;247c	ff		.
	rst 38h			;247d	ff		.
	rst 38h			;247e	ff		.
	rst 38h			;247f	ff		.
	rst 38h			;2480	ff		.
	rst 38h			;2481	ff		.
	rst 38h			;2482	ff		.
	rst 38h			;2483	ff		.
	rst 38h			;2484	ff		.
	rst 38h			;2485	ff		.
	rst 38h			;2486	ff		.
	rst 38h			;2487	ff		.
	rst 38h			;2488	ff		.
	rst 38h			;2489	ff		.
	rst 38h			;248a	ff		.
	rst 38h			;248b	ff		.
	rst 38h			;248c	ff		.
	rst 38h			;248d	ff		.
	rst 38h			;248e	ff		.
	rst 38h			;248f	ff		.
	rst 38h			;2490	ff		.
	rst 38h			;2491	ff		.
	rst 38h			;2492	ff		.
	rst 38h			;2493	ff		.
	rst 38h			;2494	ff		.
	rst 38h			;2495	ff		.
	rst 38h			;2496	ff		.
	rst 38h			;2497	ff		.
	rst 38h			;2498	ff		.
	rst 38h			;2499	ff		.
	rst 38h			;249a	ff		.
	rst 38h			;249b	ff		.
	rst 38h			;249c	ff		.
	rst 38h			;249d	ff		.
	rst 38h			;249e	ff		.
	rst 38h			;249f	ff		.
	rst 38h			;24a0	ff		.
	rst 38h			;24a1	ff		.
	rst 38h			;24a2	ff		.
	rst 38h			;24a3	ff		.
	rst 38h			;24a4	ff		.
	rst 38h			;24a5	ff		.
	rst 38h			;24a6	ff		.
	rst 38h			;24a7	ff		.
	rst 38h			;24a8	ff		.
	rst 38h			;24a9	ff		.
	rst 38h			;24aa	ff		.
	rst 38h			;24ab	ff		.
	rst 38h			;24ac	ff		.
	rst 38h			;24ad	ff		.
	rst 38h			;24ae	ff		.
	rst 38h			;24af	ff		.
	rst 38h			;24b0	ff		.
	rst 38h			;24b1	ff		.
	rst 38h			;24b2	ff		.
	rst 38h			;24b3	ff		.
	rst 38h			;24b4	ff		.
	rst 38h			;24b5	ff		.
	rst 38h			;24b6	ff		.
	rst 38h			;24b7	ff		.
	rst 38h			;24b8	ff		.
	rst 38h			;24b9	ff		.
	rst 38h			;24ba	ff		.
	rst 38h			;24bb	ff		.
	rst 38h			;24bc	ff		.
	rst 38h			;24bd	ff		.
	rst 38h			;24be	ff		.
	rst 38h			;24bf	ff		.
	rst 38h			;24c0	ff		.
	rst 38h			;24c1	ff		.
	rst 38h			;24c2	ff		.
	rst 38h			;24c3	ff		.
	rst 38h			;24c4	ff		.
	rst 38h			;24c5	ff		.
	rst 38h			;24c6	ff		.
l24c7h:
	rst 38h			;24c7	ff		.
	rst 38h			;24c8	ff		.
	rst 38h			;24c9	ff		.
	rst 38h			;24ca	ff		.
	rst 38h			;24cb	ff		.
	rst 38h			;24cc	ff		.
	rst 38h			;24cd	ff		.
	rst 38h			;24ce	ff		.
	rst 38h			;24cf	ff		.
	rst 38h			;24d0	ff		.
	rst 38h			;24d1	ff		.
	rst 38h			;24d2	ff		.
	rst 38h			;24d3	ff		.
	rst 38h			;24d4	ff		.
	rst 38h			;24d5	ff		.
	rst 38h			;24d6	ff		.
	rst 38h			;24d7	ff		.
	rst 38h			;24d8	ff		.
	rst 38h			;24d9	ff		.
	rst 38h			;24da	ff		.
	rst 38h			;24db	ff		.
	rst 38h			;24dc	ff		.
	rst 38h			;24dd	ff		.
	rst 38h			;24de	ff		.
	rst 38h			;24df	ff		.
	rst 38h			;24e0	ff		.
	rst 38h			;24e1	ff		.
	rst 38h			;24e2	ff		.
	rst 38h			;24e3	ff		.
	rst 38h			;24e4	ff		.
	rst 38h			;24e5	ff		.
	rst 38h			;24e6	ff		.
	rst 38h			;24e7	ff		.
	rst 38h			;24e8	ff		.
	rst 38h			;24e9	ff		.
	rst 38h			;24ea	ff		.
	rst 38h			;24eb	ff		.
	rst 38h			;24ec	ff		.
	rst 38h			;24ed	ff		.
	rst 38h			;24ee	ff		.
	rst 38h			;24ef	ff		.
	rst 38h			;24f0	ff		.
	rst 38h			;24f1	ff		.
	rst 38h			;24f2	ff		.
	rst 38h			;24f3	ff		.
	rst 38h			;24f4	ff		.
	rst 38h			;24f5	ff		.
	rst 38h			;24f6	ff		.
	rst 38h			;24f7	ff		.
	rst 38h			;24f8	ff		.
	rst 38h			;24f9	ff		.
	rst 38h			;24fa	ff		.
	rst 38h			;24fb	ff		.
	rst 38h			;24fc	ff		.
	rst 38h			;24fd	ff		.
	rst 38h			;24fe	ff		.
	rst 38h			;24ff	ff		.
	rst 38h			;2500	ff		.
	rst 38h			;2501	ff		.
	rst 38h			;2502	ff		.
	rst 38h			;2503	ff		.
	rst 38h			;2504	ff		.
	rst 38h			;2505	ff		.
	rst 38h			;2506	ff		.
	rst 38h			;2507	ff		.
	rst 38h			;2508	ff		.
	rst 38h			;2509	ff		.
	rst 38h			;250a	ff		.
	rst 38h			;250b	ff		.
	rst 38h			;250c	ff		.
	rst 38h			;250d	ff		.
	rst 38h			;250e	ff		.
	rst 38h			;250f	ff		.
	rst 38h			;2510	ff		.
	rst 38h			;2511	ff		.
	rst 38h			;2512	ff		.
	rst 38h			;2513	ff		.
	rst 38h			;2514	ff		.
	rst 38h			;2515	ff		.
	rst 38h			;2516	ff		.
	rst 38h			;2517	ff		.
	rst 38h			;2518	ff		.
	rst 38h			;2519	ff		.
	rst 38h			;251a	ff		.
	rst 38h			;251b	ff		.
	rst 38h			;251c	ff		.
	rst 38h			;251d	ff		.
	rst 38h			;251e	ff		.
	rst 38h			;251f	ff		.
	rst 38h			;2520	ff		.
	rst 38h			;2521	ff		.
	rst 38h			;2522	ff		.
	rst 38h			;2523	ff		.
	rst 38h			;2524	ff		.
	rst 38h			;2525	ff		.
	rst 38h			;2526	ff		.
	rst 38h			;2527	ff		.
	rst 38h			;2528	ff		.
	rst 38h			;2529	ff		.
	rst 38h			;252a	ff		.
	rst 38h			;252b	ff		.
	rst 38h			;252c	ff		.
	rst 38h			;252d	ff		.
	rst 38h			;252e	ff		.
	rst 38h			;252f	ff		.
	rst 38h			;2530	ff		.
	rst 38h			;2531	ff		.
	rst 38h			;2532	ff		.
	rst 38h			;2533	ff		.
	rst 38h			;2534	ff		.
	rst 38h			;2535	ff		.
	rst 38h			;2536	ff		.
	rst 38h			;2537	ff		.
	rst 38h			;2538	ff		.
	rst 38h			;2539	ff		.
	rst 38h			;253a	ff		.
	rst 38h			;253b	ff		.
	rst 38h			;253c	ff		.
	rst 38h			;253d	ff		.
	rst 38h			;253e	ff		.
	rst 38h			;253f	ff		.
	rst 38h			;2540	ff		.
	rst 38h			;2541	ff		.
	rst 38h			;2542	ff		.
	rst 38h			;2543	ff		.
	rst 38h			;2544	ff		.
	rst 38h			;2545	ff		.
	rst 38h			;2546	ff		.
	rst 38h			;2547	ff		.
	rst 38h			;2548	ff		.
	rst 38h			;2549	ff		.
	rst 38h			;254a	ff		.
	rst 38h			;254b	ff		.
	rst 38h			;254c	ff		.
	rst 38h			;254d	ff		.
	rst 38h			;254e	ff		.
l254fh:
	rst 38h			;254f	ff		.
	rst 38h			;2550	ff		.
	rst 38h			;2551	ff		.
	rst 38h			;2552	ff		.
	rst 38h			;2553	ff		.
	rst 38h			;2554	ff		.
	rst 38h			;2555	ff		.
	rst 38h			;2556	ff		.
	rst 38h			;2557	ff		.
l2558h:
	rst 38h			;2558	ff		.
	rst 38h			;2559	ff		.
	rst 38h			;255a	ff		.
	rst 38h			;255b	ff		.
	rst 38h			;255c	ff		.
	rst 38h			;255d	ff		.
	rst 38h			;255e	ff		.
	rst 38h			;255f	ff		.
	rst 38h			;2560	ff		.
	rst 38h			;2561	ff		.
	rst 38h			;2562	ff		.
	rst 38h			;2563	ff		.
	rst 38h			;2564	ff		.
	rst 38h			;2565	ff		.
	rst 38h			;2566	ff		.
	rst 38h			;2567	ff		.
	rst 38h			;2568	ff		.
sub_2569h:
	rst 38h			;2569	ff		.
	rst 38h			;256a	ff		.
	rst 38h			;256b	ff		.
	rst 38h			;256c	ff		.
	rst 38h			;256d	ff		.
	rst 38h			;256e	ff		.
	rst 38h			;256f	ff		.
	rst 38h			;2570	ff		.
	rst 38h			;2571	ff		.
	rst 38h			;2572	ff		.
	rst 38h			;2573	ff		.
	rst 38h			;2574	ff		.
	rst 38h			;2575	ff		.
	rst 38h			;2576	ff		.
	rst 38h			;2577	ff		.
	rst 38h			;2578	ff		.
	rst 38h			;2579	ff		.
	rst 38h			;257a	ff		.
	rst 38h			;257b	ff		.
	rst 38h			;257c	ff		.
	rst 38h			;257d	ff		.
	rst 38h			;257e	ff		.
	rst 38h			;257f	ff		.
	rst 38h			;2580	ff		.
	rst 38h			;2581	ff		.
	rst 38h			;2582	ff		.
	rst 38h			;2583	ff		.
	rst 38h			;2584	ff		.
	rst 38h			;2585	ff		.
	rst 38h			;2586	ff		.
	rst 38h			;2587	ff		.
	rst 38h			;2588	ff		.
	rst 38h			;2589	ff		.
	rst 38h			;258a	ff		.
	rst 38h			;258b	ff		.
	rst 38h			;258c	ff		.
	rst 38h			;258d	ff		.
	rst 38h			;258e	ff		.
	rst 38h			;258f	ff		.
	rst 38h			;2590	ff		.
	rst 38h			;2591	ff		.
	rst 38h			;2592	ff		.
	rst 38h			;2593	ff		.
	rst 38h			;2594	ff		.
	rst 38h			;2595	ff		.
	rst 38h			;2596	ff		.
	rst 38h			;2597	ff		.
	rst 38h			;2598	ff		.
	rst 38h			;2599	ff		.
	rst 38h			;259a	ff		.
	rst 38h			;259b	ff		.
	rst 38h			;259c	ff		.
	rst 38h			;259d	ff		.
	rst 38h			;259e	ff		.
	rst 38h			;259f	ff		.
	rst 38h			;25a0	ff		.
	rst 38h			;25a1	ff		.
	rst 38h			;25a2	ff		.
	rst 38h			;25a3	ff		.
	rst 38h			;25a4	ff		.
	rst 38h			;25a5	ff		.
	rst 38h			;25a6	ff		.
	rst 38h			;25a7	ff		.
	rst 38h			;25a8	ff		.
	rst 38h			;25a9	ff		.
	rst 38h			;25aa	ff		.
	rst 38h			;25ab	ff		.
	rst 38h			;25ac	ff		.
	rst 38h			;25ad	ff		.
	rst 38h			;25ae	ff		.
	rst 38h			;25af	ff		.
	rst 38h			;25b0	ff		.
	rst 38h			;25b1	ff		.
	rst 38h			;25b2	ff		.
	rst 38h			;25b3	ff		.
	rst 38h			;25b4	ff		.
	rst 38h			;25b5	ff		.
	rst 38h			;25b6	ff		.
	rst 38h			;25b7	ff		.
	rst 38h			;25b8	ff		.
	rst 38h			;25b9	ff		.
	rst 38h			;25ba	ff		.
	rst 38h			;25bb	ff		.
	rst 38h			;25bc	ff		.
	rst 38h			;25bd	ff		.
	rst 38h			;25be	ff		.
	rst 38h			;25bf	ff		.
	rst 38h			;25c0	ff		.
	rst 38h			;25c1	ff		.
	rst 38h			;25c2	ff		.
	rst 38h			;25c3	ff		.
	rst 38h			;25c4	ff		.
	rst 38h			;25c5	ff		.
	rst 38h			;25c6	ff		.
	rst 38h			;25c7	ff		.
	rst 38h			;25c8	ff		.
	rst 38h			;25c9	ff		.
	rst 38h			;25ca	ff		.
	rst 38h			;25cb	ff		.
	rst 38h			;25cc	ff		.
	rst 38h			;25cd	ff		.
	rst 38h			;25ce	ff		.
	rst 38h			;25cf	ff		.
	rst 38h			;25d0	ff		.
	rst 38h			;25d1	ff		.
	rst 38h			;25d2	ff		.
	rst 38h			;25d3	ff		.
	rst 38h			;25d4	ff		.
	rst 38h			;25d5	ff		.
	rst 38h			;25d6	ff		.
	rst 38h			;25d7	ff		.
	rst 38h			;25d8	ff		.
	rst 38h			;25d9	ff		.
	rst 38h			;25da	ff		.
	rst 38h			;25db	ff		.
	rst 38h			;25dc	ff		.
	rst 38h			;25dd	ff		.
	rst 38h			;25de	ff		.
	rst 38h			;25df	ff		.
	rst 38h			;25e0	ff		.
	rst 38h			;25e1	ff		.
	rst 38h			;25e2	ff		.
	rst 38h			;25e3	ff		.
	rst 38h			;25e4	ff		.
	rst 38h			;25e5	ff		.
	rst 38h			;25e6	ff		.
	rst 38h			;25e7	ff		.
	rst 38h			;25e8	ff		.
	rst 38h			;25e9	ff		.
	rst 38h			;25ea	ff		.
	rst 38h			;25eb	ff		.
	rst 38h			;25ec	ff		.
	rst 38h			;25ed	ff		.
	rst 38h			;25ee	ff		.
	rst 38h			;25ef	ff		.
	rst 38h			;25f0	ff		.
	rst 38h			;25f1	ff		.
	rst 38h			;25f2	ff		.
	rst 38h			;25f3	ff		.
	rst 38h			;25f4	ff		.
	rst 38h			;25f5	ff		.
	rst 38h			;25f6	ff		.
	rst 38h			;25f7	ff		.
	rst 38h			;25f8	ff		.
	rst 38h			;25f9	ff		.
	rst 38h			;25fa	ff		.
	rst 38h			;25fb	ff		.
	rst 38h			;25fc	ff		.
	rst 38h			;25fd	ff		.
	rst 38h			;25fe	ff		.
	rst 38h			;25ff	ff		.
	rst 38h			;2600	ff		.
	rst 38h			;2601	ff		.
	rst 38h			;2602	ff		.
	rst 38h			;2603	ff		.
	rst 38h			;2604	ff		.
	rst 38h			;2605	ff		.
	rst 38h			;2606	ff		.
	rst 38h			;2607	ff		.
	rst 38h			;2608	ff		.
	rst 38h			;2609	ff		.
	rst 38h			;260a	ff		.
	rst 38h			;260b	ff		.
	rst 38h			;260c	ff		.
	rst 38h			;260d	ff		.
	rst 38h			;260e	ff		.
	rst 38h			;260f	ff		.
	rst 38h			;2610	ff		.
	rst 38h			;2611	ff		.
	rst 38h			;2612	ff		.
	rst 38h			;2613	ff		.
	rst 38h			;2614	ff		.
	rst 38h			;2615	ff		.
	rst 38h			;2616	ff		.
	rst 38h			;2617	ff		.
	rst 38h			;2618	ff		.
	rst 38h			;2619	ff		.
	rst 38h			;261a	ff		.
	rst 38h			;261b	ff		.
	rst 38h			;261c	ff		.
	rst 38h			;261d	ff		.
	rst 38h			;261e	ff		.
	rst 38h			;261f	ff		.
	rst 38h			;2620	ff		.
	rst 38h			;2621	ff		.
	rst 38h			;2622	ff		.
	rst 38h			;2623	ff		.
	rst 38h			;2624	ff		.
	rst 38h			;2625	ff		.
	rst 38h			;2626	ff		.
	rst 38h			;2627	ff		.
	rst 38h			;2628	ff		.
	rst 38h			;2629	ff		.
	rst 38h			;262a	ff		.
	rst 38h			;262b	ff		.
	rst 38h			;262c	ff		.
	rst 38h			;262d	ff		.
	rst 38h			;262e	ff		.
	rst 38h			;262f	ff		.
	rst 38h			;2630	ff		.
	rst 38h			;2631	ff		.
	rst 38h			;2632	ff		.
	rst 38h			;2633	ff		.
	rst 38h			;2634	ff		.
	rst 38h			;2635	ff		.
	rst 38h			;2636	ff		.
	rst 38h			;2637	ff		.
	rst 38h			;2638	ff		.
	rst 38h			;2639	ff		.
	rst 38h			;263a	ff		.
	rst 38h			;263b	ff		.
	rst 38h			;263c	ff		.
	rst 38h			;263d	ff		.
	rst 38h			;263e	ff		.
	rst 38h			;263f	ff		.
	rst 38h			;2640	ff		.
	rst 38h			;2641	ff		.
	rst 38h			;2642	ff		.
	rst 38h			;2643	ff		.
	rst 38h			;2644	ff		.
	rst 38h			;2645	ff		.
	rst 38h			;2646	ff		.
	rst 38h			;2647	ff		.
	rst 38h			;2648	ff		.
	rst 38h			;2649	ff		.
	rst 38h			;264a	ff		.
	rst 38h			;264b	ff		.
	rst 38h			;264c	ff		.
	rst 38h			;264d	ff		.
	rst 38h			;264e	ff		.
	rst 38h			;264f	ff		.
	rst 38h			;2650	ff		.
	rst 38h			;2651	ff		.
	rst 38h			;2652	ff		.
	rst 38h			;2653	ff		.
	rst 38h			;2654	ff		.
	rst 38h			;2655	ff		.
	rst 38h			;2656	ff		.
	rst 38h			;2657	ff		.
	rst 38h			;2658	ff		.
	rst 38h			;2659	ff		.
	rst 38h			;265a	ff		.
	rst 38h			;265b	ff		.
	rst 38h			;265c	ff		.
	rst 38h			;265d	ff		.
	rst 38h			;265e	ff		.
	rst 38h			;265f	ff		.
	rst 38h			;2660	ff		.
	rst 38h			;2661	ff		.
	rst 38h			;2662	ff		.
	rst 38h			;2663	ff		.
	rst 38h			;2664	ff		.
	rst 38h			;2665	ff		.
	rst 38h			;2666	ff		.
	rst 38h			;2667	ff		.
	rst 38h			;2668	ff		.
	rst 38h			;2669	ff		.
	rst 38h			;266a	ff		.
	rst 38h			;266b	ff		.
	rst 38h			;266c	ff		.
	rst 38h			;266d	ff		.
	rst 38h			;266e	ff		.
	rst 38h			;266f	ff		.
	rst 38h			;2670	ff		.
	rst 38h			;2671	ff		.
	rst 38h			;2672	ff		.
	rst 38h			;2673	ff		.
	rst 38h			;2674	ff		.
	rst 38h			;2675	ff		.
	rst 38h			;2676	ff		.
	rst 38h			;2677	ff		.
	rst 38h			;2678	ff		.
	rst 38h			;2679	ff		.
	rst 38h			;267a	ff		.
	rst 38h			;267b	ff		.
	rst 38h			;267c	ff		.
	rst 38h			;267d	ff		.
	rst 38h			;267e	ff		.
	rst 38h			;267f	ff		.
	rst 38h			;2680	ff		.
	rst 38h			;2681	ff		.
	rst 38h			;2682	ff		.
	rst 38h			;2683	ff		.
	rst 38h			;2684	ff		.
	rst 38h			;2685	ff		.
	rst 38h			;2686	ff		.
	rst 38h			;2687	ff		.
	rst 38h			;2688	ff		.
	rst 38h			;2689	ff		.
	rst 38h			;268a	ff		.
	rst 38h			;268b	ff		.
	rst 38h			;268c	ff		.
	rst 38h			;268d	ff		.
	rst 38h			;268e	ff		.
	rst 38h			;268f	ff		.
	rst 38h			;2690	ff		.
	rst 38h			;2691	ff		.
	rst 38h			;2692	ff		.
	rst 38h			;2693	ff		.
	rst 38h			;2694	ff		.
	rst 38h			;2695	ff		.
	rst 38h			;2696	ff		.
	rst 38h			;2697	ff		.
	rst 38h			;2698	ff		.
	rst 38h			;2699	ff		.
	rst 38h			;269a	ff		.
	rst 38h			;269b	ff		.
	rst 38h			;269c	ff		.
	rst 38h			;269d	ff		.
	rst 38h			;269e	ff		.
	rst 38h			;269f	ff		.
	rst 38h			;26a0	ff		.
	rst 38h			;26a1	ff		.
	rst 38h			;26a2	ff		.
	rst 38h			;26a3	ff		.
	rst 38h			;26a4	ff		.
	rst 38h			;26a5	ff		.
	rst 38h			;26a6	ff		.
	rst 38h			;26a7	ff		.
	rst 38h			;26a8	ff		.
	rst 38h			;26a9	ff		.
	rst 38h			;26aa	ff		.
	rst 38h			;26ab	ff		.
	rst 38h			;26ac	ff		.
	rst 38h			;26ad	ff		.
	rst 38h			;26ae	ff		.
	rst 38h			;26af	ff		.
	rst 38h			;26b0	ff		.
	rst 38h			;26b1	ff		.
	rst 38h			;26b2	ff		.
	rst 38h			;26b3	ff		.
	rst 38h			;26b4	ff		.
	rst 38h			;26b5	ff		.
	rst 38h			;26b6	ff		.
	rst 38h			;26b7	ff		.
	rst 38h			;26b8	ff		.
	rst 38h			;26b9	ff		.
	rst 38h			;26ba	ff		.
	rst 38h			;26bb	ff		.
	rst 38h			;26bc	ff		.
	rst 38h			;26bd	ff		.
	rst 38h			;26be	ff		.
	rst 38h			;26bf	ff		.
	rst 38h			;26c0	ff		.
	rst 38h			;26c1	ff		.
	rst 38h			;26c2	ff		.
	rst 38h			;26c3	ff		.
	rst 38h			;26c4	ff		.
	rst 38h			;26c5	ff		.
	rst 38h			;26c6	ff		.
	rst 38h			;26c7	ff		.
	rst 38h			;26c8	ff		.
	rst 38h			;26c9	ff		.
	rst 38h			;26ca	ff		.
	rst 38h			;26cb	ff		.
	rst 38h			;26cc	ff		.
	rst 38h			;26cd	ff		.
	rst 38h			;26ce	ff		.
	rst 38h			;26cf	ff		.
	rst 38h			;26d0	ff		.
	rst 38h			;26d1	ff		.
	rst 38h			;26d2	ff		.
	rst 38h			;26d3	ff		.
	rst 38h			;26d4	ff		.
	rst 38h			;26d5	ff		.
	rst 38h			;26d6	ff		.
	rst 38h			;26d7	ff		.
	rst 38h			;26d8	ff		.
	rst 38h			;26d9	ff		.
	rst 38h			;26da	ff		.
	rst 38h			;26db	ff		.
	rst 38h			;26dc	ff		.
	rst 38h			;26dd	ff		.
	rst 38h			;26de	ff		.
	rst 38h			;26df	ff		.
	rst 38h			;26e0	ff		.
	rst 38h			;26e1	ff		.
	rst 38h			;26e2	ff		.
	rst 38h			;26e3	ff		.
	rst 38h			;26e4	ff		.
	rst 38h			;26e5	ff		.
	rst 38h			;26e6	ff		.
	rst 38h			;26e7	ff		.
	rst 38h			;26e8	ff		.
	rst 38h			;26e9	ff		.
	rst 38h			;26ea	ff		.
	rst 38h			;26eb	ff		.
	rst 38h			;26ec	ff		.
	rst 38h			;26ed	ff		.
	rst 38h			;26ee	ff		.
	rst 38h			;26ef	ff		.
	rst 38h			;26f0	ff		.
	rst 38h			;26f1	ff		.
	rst 38h			;26f2	ff		.
	rst 38h			;26f3	ff		.
	rst 38h			;26f4	ff		.
	rst 38h			;26f5	ff		.
	rst 38h			;26f6	ff		.
	rst 38h			;26f7	ff		.
	rst 38h			;26f8	ff		.
	rst 38h			;26f9	ff		.
	rst 38h			;26fa	ff		.
	rst 38h			;26fb	ff		.
	rst 38h			;26fc	ff		.
	rst 38h			;26fd	ff		.
	rst 38h			;26fe	ff		.
	rst 38h			;26ff	ff		.
	rst 38h			;2700	ff		.
	rst 38h			;2701	ff		.
	rst 38h			;2702	ff		.
	rst 38h			;2703	ff		.
	rst 38h			;2704	ff		.
	rst 38h			;2705	ff		.
	rst 38h			;2706	ff		.
	rst 38h			;2707	ff		.
	rst 38h			;2708	ff		.
	rst 38h			;2709	ff		.
	rst 38h			;270a	ff		.
	rst 38h			;270b	ff		.
	rst 38h			;270c	ff		.
	rst 38h			;270d	ff		.
	rst 38h			;270e	ff		.
	rst 38h			;270f	ff		.
	rst 38h			;2710	ff		.
	rst 38h			;2711	ff		.
	rst 38h			;2712	ff		.
	rst 38h			;2713	ff		.
	rst 38h			;2714	ff		.
	rst 38h			;2715	ff		.
	rst 38h			;2716	ff		.
	rst 38h			;2717	ff		.
	rst 38h			;2718	ff		.
	rst 38h			;2719	ff		.
	rst 38h			;271a	ff		.
	rst 38h			;271b	ff		.
	rst 38h			;271c	ff		.
	rst 38h			;271d	ff		.
	rst 38h			;271e	ff		.
	rst 38h			;271f	ff		.
	rst 38h			;2720	ff		.
	rst 38h			;2721	ff		.
	rst 38h			;2722	ff		.
	rst 38h			;2723	ff		.
	rst 38h			;2724	ff		.
	rst 38h			;2725	ff		.
	rst 38h			;2726	ff		.
	rst 38h			;2727	ff		.
	rst 38h			;2728	ff		.
	rst 38h			;2729	ff		.
	rst 38h			;272a	ff		.
	rst 38h			;272b	ff		.
	rst 38h			;272c	ff		.
	rst 38h			;272d	ff		.
	rst 38h			;272e	ff		.
	rst 38h			;272f	ff		.
	rst 38h			;2730	ff		.
	rst 38h			;2731	ff		.
	rst 38h			;2732	ff		.
	rst 38h			;2733	ff		.
	rst 38h			;2734	ff		.
	rst 38h			;2735	ff		.
	rst 38h			;2736	ff		.
	rst 38h			;2737	ff		.
	rst 38h			;2738	ff		.
	rst 38h			;2739	ff		.
	rst 38h			;273a	ff		.
	rst 38h			;273b	ff		.
	rst 38h			;273c	ff		.
	rst 38h			;273d	ff		.
	rst 38h			;273e	ff		.
	rst 38h			;273f	ff		.
	rst 38h			;2740	ff		.
	rst 38h			;2741	ff		.
	rst 38h			;2742	ff		.
	rst 38h			;2743	ff		.
	rst 38h			;2744	ff		.
	rst 38h			;2745	ff		.
	rst 38h			;2746	ff		.
	rst 38h			;2747	ff		.
	rst 38h			;2748	ff		.
	rst 38h			;2749	ff		.
	rst 38h			;274a	ff		.
	rst 38h			;274b	ff		.
	rst 38h			;274c	ff		.
	rst 38h			;274d	ff		.
	rst 38h			;274e	ff		.
	rst 38h			;274f	ff		.
	rst 38h			;2750	ff		.
	rst 38h			;2751	ff		.
	rst 38h			;2752	ff		.
	rst 38h			;2753	ff		.
	rst 38h			;2754	ff		.
	rst 38h			;2755	ff		.
	rst 38h			;2756	ff		.
	rst 38h			;2757	ff		.
	rst 38h			;2758	ff		.
	rst 38h			;2759	ff		.
	rst 38h			;275a	ff		.
	rst 38h			;275b	ff		.
	rst 38h			;275c	ff		.
	rst 38h			;275d	ff		.
	rst 38h			;275e	ff		.
	rst 38h			;275f	ff		.
	rst 38h			;2760	ff		.
	rst 38h			;2761	ff		.
	rst 38h			;2762	ff		.
	rst 38h			;2763	ff		.
	rst 38h			;2764	ff		.
	rst 38h			;2765	ff		.
	rst 38h			;2766	ff		.
	rst 38h			;2767	ff		.
	rst 38h			;2768	ff		.
	rst 38h			;2769	ff		.
	rst 38h			;276a	ff		.
	rst 38h			;276b	ff		.
	rst 38h			;276c	ff		.
	rst 38h			;276d	ff		.
	rst 38h			;276e	ff		.
	rst 38h			;276f	ff		.
	rst 38h			;2770	ff		.
	rst 38h			;2771	ff		.
	rst 38h			;2772	ff		.
	rst 38h			;2773	ff		.
	rst 38h			;2774	ff		.
	rst 38h			;2775	ff		.
	rst 38h			;2776	ff		.
	rst 38h			;2777	ff		.
	rst 38h			;2778	ff		.
	rst 38h			;2779	ff		.
	rst 38h			;277a	ff		.
	rst 38h			;277b	ff		.
	rst 38h			;277c	ff		.
	rst 38h			;277d	ff		.
	rst 38h			;277e	ff		.
	rst 38h			;277f	ff		.
	rst 38h			;2780	ff		.
	rst 38h			;2781	ff		.
	rst 38h			;2782	ff		.
	rst 38h			;2783	ff		.
	rst 38h			;2784	ff		.
	rst 38h			;2785	ff		.
	rst 38h			;2786	ff		.
	rst 38h			;2787	ff		.
	rst 38h			;2788	ff		.
	rst 38h			;2789	ff		.
	rst 38h			;278a	ff		.
	rst 38h			;278b	ff		.
	rst 38h			;278c	ff		.
	rst 38h			;278d	ff		.
	rst 38h			;278e	ff		.
	rst 38h			;278f	ff		.
	rst 38h			;2790	ff		.
	rst 38h			;2791	ff		.
	rst 38h			;2792	ff		.
	rst 38h			;2793	ff		.
	rst 38h			;2794	ff		.
	rst 38h			;2795	ff		.
	rst 38h			;2796	ff		.
	rst 38h			;2797	ff		.
	rst 38h			;2798	ff		.
	rst 38h			;2799	ff		.
	rst 38h			;279a	ff		.
	rst 38h			;279b	ff		.
	rst 38h			;279c	ff		.
	rst 38h			;279d	ff		.
	rst 38h			;279e	ff		.
	rst 38h			;279f	ff		.
	rst 38h			;27a0	ff		.
	rst 38h			;27a1	ff		.
	rst 38h			;27a2	ff		.
	rst 38h			;27a3	ff		.
	rst 38h			;27a4	ff		.
	rst 38h			;27a5	ff		.
	rst 38h			;27a6	ff		.
	rst 38h			;27a7	ff		.
	rst 38h			;27a8	ff		.
	rst 38h			;27a9	ff		.
	rst 38h			;27aa	ff		.
	rst 38h			;27ab	ff		.
	rst 38h			;27ac	ff		.
	rst 38h			;27ad	ff		.
	rst 38h			;27ae	ff		.
	rst 38h			;27af	ff		.
	rst 38h			;27b0	ff		.
	rst 38h			;27b1	ff		.
	rst 38h			;27b2	ff		.
	rst 38h			;27b3	ff		.
	rst 38h			;27b4	ff		.
	rst 38h			;27b5	ff		.
	rst 38h			;27b6	ff		.
	rst 38h			;27b7	ff		.
	rst 38h			;27b8	ff		.
	rst 38h			;27b9	ff		.
	rst 38h			;27ba	ff		.
	rst 38h			;27bb	ff		.
	rst 38h			;27bc	ff		.
	rst 38h			;27bd	ff		.
	rst 38h			;27be	ff		.
	rst 38h			;27bf	ff		.
	rst 38h			;27c0	ff		.
	rst 38h			;27c1	ff		.
	rst 38h			;27c2	ff		.
	rst 38h			;27c3	ff		.
	rst 38h			;27c4	ff		.
	rst 38h			;27c5	ff		.
	rst 38h			;27c6	ff		.
	rst 38h			;27c7	ff		.
	rst 38h			;27c8	ff		.
	rst 38h			;27c9	ff		.
	rst 38h			;27ca	ff		.
	rst 38h			;27cb	ff		.
	rst 38h			;27cc	ff		.
	rst 38h			;27cd	ff		.
	rst 38h			;27ce	ff		.
	rst 38h			;27cf	ff		.
	rst 38h			;27d0	ff		.
	rst 38h			;27d1	ff		.
	rst 38h			;27d2	ff		.
	rst 38h			;27d3	ff		.
	rst 38h			;27d4	ff		.
	rst 38h			;27d5	ff		.
	rst 38h			;27d6	ff		.
	rst 38h			;27d7	ff		.
	rst 38h			;27d8	ff		.
	rst 38h			;27d9	ff		.
	rst 38h			;27da	ff		.
	rst 38h			;27db	ff		.
	rst 38h			;27dc	ff		.
	rst 38h			;27dd	ff		.
	rst 38h			;27de	ff		.
	rst 38h			;27df	ff		.
	rst 38h			;27e0	ff		.
	rst 38h			;27e1	ff		.
	rst 38h			;27e2	ff		.
	rst 38h			;27e3	ff		.
	rst 38h			;27e4	ff		.
	rst 38h			;27e5	ff		.
	rst 38h			;27e6	ff		.
	rst 38h			;27e7	ff		.
	rst 38h			;27e8	ff		.
	rst 38h			;27e9	ff		.
	rst 38h			;27ea	ff		.
	rst 38h			;27eb	ff		.
	rst 38h			;27ec	ff		.
	rst 38h			;27ed	ff		.
	rst 38h			;27ee	ff		.
	rst 38h			;27ef	ff		.
	rst 38h			;27f0	ff		.
	rst 38h			;27f1	ff		.
	rst 38h			;27f2	ff		.
	rst 38h			;27f3	ff		.
	rst 38h			;27f4	ff		.
	rst 38h			;27f5	ff		.
	rst 38h			;27f6	ff		.
	rst 38h			;27f7	ff		.
	rst 38h			;27f8	ff		.
	rst 38h			;27f9	ff		.
	rst 38h			;27fa	ff		.
	rst 38h			;27fb	ff		.
	rst 38h			;27fc	ff		.
	rst 38h			;27fd	ff		.
	rst 38h			;27fe	ff		.
	rst 38h			;27ff	ff		.
	rst 38h			;2800	ff		.
	rst 38h			;2801	ff		.
	rst 38h			;2802	ff		.
	rst 38h			;2803	ff		.
	rst 38h			;2804	ff		.
	rst 38h			;2805	ff		.
	rst 38h			;2806	ff		.
	rst 38h			;2807	ff		.
	rst 38h			;2808	ff		.
	rst 38h			;2809	ff		.
	rst 38h			;280a	ff		.
	rst 38h			;280b	ff		.
	rst 38h			;280c	ff		.
	rst 38h			;280d	ff		.
	rst 38h			;280e	ff		.
	rst 38h			;280f	ff		.
	rst 38h			;2810	ff		.
	rst 38h			;2811	ff		.
	rst 38h			;2812	ff		.
	rst 38h			;2813	ff		.
	rst 38h			;2814	ff		.
	rst 38h			;2815	ff		.
	rst 38h			;2816	ff		.
	rst 38h			;2817	ff		.
	rst 38h			;2818	ff		.
	rst 38h			;2819	ff		.
	rst 38h			;281a	ff		.
	rst 38h			;281b	ff		.
	rst 38h			;281c	ff		.
	rst 38h			;281d	ff		.
	rst 38h			;281e	ff		.
	rst 38h			;281f	ff		.
	rst 38h			;2820	ff		.
	rst 38h			;2821	ff		.
	rst 38h			;2822	ff		.
	rst 38h			;2823	ff		.
	rst 38h			;2824	ff		.
	rst 38h			;2825	ff		.
	rst 38h			;2826	ff		.
	rst 38h			;2827	ff		.
	rst 38h			;2828	ff		.
	rst 38h			;2829	ff		.
	rst 38h			;282a	ff		.
	rst 38h			;282b	ff		.
	rst 38h			;282c	ff		.
	rst 38h			;282d	ff		.
	rst 38h			;282e	ff		.
	rst 38h			;282f	ff		.
	rst 38h			;2830	ff		.
	rst 38h			;2831	ff		.
	rst 38h			;2832	ff		.
	rst 38h			;2833	ff		.
	rst 38h			;2834	ff		.
	rst 38h			;2835	ff		.
	rst 38h			;2836	ff		.
	rst 38h			;2837	ff		.
	rst 38h			;2838	ff		.
	rst 38h			;2839	ff		.
	rst 38h			;283a	ff		.
	rst 38h			;283b	ff		.
	rst 38h			;283c	ff		.
	rst 38h			;283d	ff		.
	rst 38h			;283e	ff		.
	rst 38h			;283f	ff		.
	rst 38h			;2840	ff		.
	rst 38h			;2841	ff		.
	rst 38h			;2842	ff		.
	rst 38h			;2843	ff		.
	rst 38h			;2844	ff		.
	rst 38h			;2845	ff		.
	rst 38h			;2846	ff		.
	rst 38h			;2847	ff		.
	rst 38h			;2848	ff		.
	rst 38h			;2849	ff		.
	rst 38h			;284a	ff		.
	rst 38h			;284b	ff		.
	rst 38h			;284c	ff		.
	rst 38h			;284d	ff		.
	rst 38h			;284e	ff		.
	rst 38h			;284f	ff		.
	rst 38h			;2850	ff		.
	rst 38h			;2851	ff		.
	rst 38h			;2852	ff		.
	rst 38h			;2853	ff		.
	rst 38h			;2854	ff		.
	rst 38h			;2855	ff		.
	rst 38h			;2856	ff		.
	rst 38h			;2857	ff		.
	rst 38h			;2858	ff		.
	rst 38h			;2859	ff		.
	rst 38h			;285a	ff		.
	rst 38h			;285b	ff		.
	rst 38h			;285c	ff		.
	rst 38h			;285d	ff		.
	rst 38h			;285e	ff		.
	rst 38h			;285f	ff		.
	rst 38h			;2860	ff		.
	rst 38h			;2861	ff		.
	rst 38h			;2862	ff		.
	rst 38h			;2863	ff		.
	rst 38h			;2864	ff		.
	rst 38h			;2865	ff		.
	rst 38h			;2866	ff		.
	rst 38h			;2867	ff		.
	rst 38h			;2868	ff		.
	rst 38h			;2869	ff		.
	rst 38h			;286a	ff		.
	rst 38h			;286b	ff		.
	rst 38h			;286c	ff		.
	rst 38h			;286d	ff		.
	rst 38h			;286e	ff		.
	rst 38h			;286f	ff		.
	rst 38h			;2870	ff		.
	rst 38h			;2871	ff		.
	rst 38h			;2872	ff		.
	rst 38h			;2873	ff		.
	rst 38h			;2874	ff		.
	rst 38h			;2875	ff		.
	rst 38h			;2876	ff		.
	rst 38h			;2877	ff		.
	rst 38h			;2878	ff		.
	rst 38h			;2879	ff		.
	rst 38h			;287a	ff		.
	rst 38h			;287b	ff		.
	rst 38h			;287c	ff		.
	rst 38h			;287d	ff		.
	rst 38h			;287e	ff		.
	rst 38h			;287f	ff		.
	rst 38h			;2880	ff		.
	rst 38h			;2881	ff		.
	rst 38h			;2882	ff		.
	rst 38h			;2883	ff		.
	rst 38h			;2884	ff		.
	rst 38h			;2885	ff		.
	rst 38h			;2886	ff		.
	rst 38h			;2887	ff		.
	rst 38h			;2888	ff		.
	rst 38h			;2889	ff		.
	rst 38h			;288a	ff		.
	rst 38h			;288b	ff		.
	rst 38h			;288c	ff		.
	rst 38h			;288d	ff		.
	rst 38h			;288e	ff		.
	rst 38h			;288f	ff		.
	rst 38h			;2890	ff		.
	rst 38h			;2891	ff		.
	rst 38h			;2892	ff		.
	rst 38h			;2893	ff		.
	rst 38h			;2894	ff		.
	rst 38h			;2895	ff		.
	rst 38h			;2896	ff		.
	rst 38h			;2897	ff		.
	rst 38h			;2898	ff		.
	rst 38h			;2899	ff		.
	rst 38h			;289a	ff		.
	rst 38h			;289b	ff		.
	rst 38h			;289c	ff		.
	rst 38h			;289d	ff		.
	rst 38h			;289e	ff		.
	rst 38h			;289f	ff		.
	rst 38h			;28a0	ff		.
	rst 38h			;28a1	ff		.
	rst 38h			;28a2	ff		.
	rst 38h			;28a3	ff		.
	rst 38h			;28a4	ff		.
	rst 38h			;28a5	ff		.
	rst 38h			;28a6	ff		.
	rst 38h			;28a7	ff		.
	rst 38h			;28a8	ff		.
	rst 38h			;28a9	ff		.
	rst 38h			;28aa	ff		.
	rst 38h			;28ab	ff		.
	rst 38h			;28ac	ff		.
	rst 38h			;28ad	ff		.
	rst 38h			;28ae	ff		.
	rst 38h			;28af	ff		.
	rst 38h			;28b0	ff		.
	rst 38h			;28b1	ff		.
	rst 38h			;28b2	ff		.
	rst 38h			;28b3	ff		.
	rst 38h			;28b4	ff		.
	rst 38h			;28b5	ff		.
	rst 38h			;28b6	ff		.
	rst 38h			;28b7	ff		.
	rst 38h			;28b8	ff		.
	rst 38h			;28b9	ff		.
	rst 38h			;28ba	ff		.
	rst 38h			;28bb	ff		.
	rst 38h			;28bc	ff		.
	rst 38h			;28bd	ff		.
	rst 38h			;28be	ff		.
	rst 38h			;28bf	ff		.
	rst 38h			;28c0	ff		.
	rst 38h			;28c1	ff		.
	rst 38h			;28c2	ff		.
	rst 38h			;28c3	ff		.
	rst 38h			;28c4	ff		.
	rst 38h			;28c5	ff		.
	rst 38h			;28c6	ff		.
	rst 38h			;28c7	ff		.
	rst 38h			;28c8	ff		.
	rst 38h			;28c9	ff		.
	rst 38h			;28ca	ff		.
	rst 38h			;28cb	ff		.
	rst 38h			;28cc	ff		.
	rst 38h			;28cd	ff		.
	rst 38h			;28ce	ff		.
	rst 38h			;28cf	ff		.
	rst 38h			;28d0	ff		.
	rst 38h			;28d1	ff		.
	rst 38h			;28d2	ff		.
	rst 38h			;28d3	ff		.
	rst 38h			;28d4	ff		.
	rst 38h			;28d5	ff		.
	rst 38h			;28d6	ff		.
	rst 38h			;28d7	ff		.
	rst 38h			;28d8	ff		.
	rst 38h			;28d9	ff		.
	rst 38h			;28da	ff		.
	rst 38h			;28db	ff		.
	rst 38h			;28dc	ff		.
	rst 38h			;28dd	ff		.
	rst 38h			;28de	ff		.
	rst 38h			;28df	ff		.
	rst 38h			;28e0	ff		.
	rst 38h			;28e1	ff		.
	rst 38h			;28e2	ff		.
	rst 38h			;28e3	ff		.
	rst 38h			;28e4	ff		.
	rst 38h			;28e5	ff		.
	rst 38h			;28e6	ff		.
	rst 38h			;28e7	ff		.
	rst 38h			;28e8	ff		.
	rst 38h			;28e9	ff		.
	rst 38h			;28ea	ff		.
	rst 38h			;28eb	ff		.
	rst 38h			;28ec	ff		.
	rst 38h			;28ed	ff		.
	rst 38h			;28ee	ff		.
	rst 38h			;28ef	ff		.
	rst 38h			;28f0	ff		.
	rst 38h			;28f1	ff		.
	rst 38h			;28f2	ff		.
	rst 38h			;28f3	ff		.
	rst 38h			;28f4	ff		.
	rst 38h			;28f5	ff		.
	rst 38h			;28f6	ff		.
	rst 38h			;28f7	ff		.
	rst 38h			;28f8	ff		.
	rst 38h			;28f9	ff		.
	rst 38h			;28fa	ff		.
	rst 38h			;28fb	ff		.
	rst 38h			;28fc	ff		.
	rst 38h			;28fd	ff		.
	rst 38h			;28fe	ff		.
	rst 38h			;28ff	ff		.
	rst 38h			;2900	ff		.
	rst 38h			;2901	ff		.
	rst 38h			;2902	ff		.
	rst 38h			;2903	ff		.
	rst 38h			;2904	ff		.
	rst 38h			;2905	ff		.
	rst 38h			;2906	ff		.
	rst 38h			;2907	ff		.
	rst 38h			;2908	ff		.
	rst 38h			;2909	ff		.
	rst 38h			;290a	ff		.
	rst 38h			;290b	ff		.
	rst 38h			;290c	ff		.
	rst 38h			;290d	ff		.
	rst 38h			;290e	ff		.
	rst 38h			;290f	ff		.
	rst 38h			;2910	ff		.
	rst 38h			;2911	ff		.
	rst 38h			;2912	ff		.
	rst 38h			;2913	ff		.
	rst 38h			;2914	ff		.
	rst 38h			;2915	ff		.
	rst 38h			;2916	ff		.
	rst 38h			;2917	ff		.
	rst 38h			;2918	ff		.
	rst 38h			;2919	ff		.
	rst 38h			;291a	ff		.
	rst 38h			;291b	ff		.
	rst 38h			;291c	ff		.
	rst 38h			;291d	ff		.
	rst 38h			;291e	ff		.
	rst 38h			;291f	ff		.
	rst 38h			;2920	ff		.
	rst 38h			;2921	ff		.
	rst 38h			;2922	ff		.
	rst 38h			;2923	ff		.
	rst 38h			;2924	ff		.
	rst 38h			;2925	ff		.
	rst 38h			;2926	ff		.
	rst 38h			;2927	ff		.
	rst 38h			;2928	ff		.
	rst 38h			;2929	ff		.
	rst 38h			;292a	ff		.
	rst 38h			;292b	ff		.
	rst 38h			;292c	ff		.
	rst 38h			;292d	ff		.
	rst 38h			;292e	ff		.
	rst 38h			;292f	ff		.
	rst 38h			;2930	ff		.
	rst 38h			;2931	ff		.
	rst 38h			;2932	ff		.
	rst 38h			;2933	ff		.
	rst 38h			;2934	ff		.
	rst 38h			;2935	ff		.
	rst 38h			;2936	ff		.
	rst 38h			;2937	ff		.
	rst 38h			;2938	ff		.
	rst 38h			;2939	ff		.
	rst 38h			;293a	ff		.
	rst 38h			;293b	ff		.
	rst 38h			;293c	ff		.
	rst 38h			;293d	ff		.
	rst 38h			;293e	ff		.
	rst 38h			;293f	ff		.
	rst 38h			;2940	ff		.
	rst 38h			;2941	ff		.
	rst 38h			;2942	ff		.
	rst 38h			;2943	ff		.
	rst 38h			;2944	ff		.
	rst 38h			;2945	ff		.
	rst 38h			;2946	ff		.
	rst 38h			;2947	ff		.
	rst 38h			;2948	ff		.
	rst 38h			;2949	ff		.
	rst 38h			;294a	ff		.
	rst 38h			;294b	ff		.
	rst 38h			;294c	ff		.
	rst 38h			;294d	ff		.
	rst 38h			;294e	ff		.
	rst 38h			;294f	ff		.
	rst 38h			;2950	ff		.
	rst 38h			;2951	ff		.
	rst 38h			;2952	ff		.
	rst 38h			;2953	ff		.
	rst 38h			;2954	ff		.
	rst 38h			;2955	ff		.
	rst 38h			;2956	ff		.
	rst 38h			;2957	ff		.
	rst 38h			;2958	ff		.
	rst 38h			;2959	ff		.
	rst 38h			;295a	ff		.
	rst 38h			;295b	ff		.
	rst 38h			;295c	ff		.
	rst 38h			;295d	ff		.
	rst 38h			;295e	ff		.
	rst 38h			;295f	ff		.
	rst 38h			;2960	ff		.
	rst 38h			;2961	ff		.
	rst 38h			;2962	ff		.
	rst 38h			;2963	ff		.
	rst 38h			;2964	ff		.
	rst 38h			;2965	ff		.
	rst 38h			;2966	ff		.
	rst 38h			;2967	ff		.
	rst 38h			;2968	ff		.
	rst 38h			;2969	ff		.
	rst 38h			;296a	ff		.
	rst 38h			;296b	ff		.
	rst 38h			;296c	ff		.
	rst 38h			;296d	ff		.
	rst 38h			;296e	ff		.
	rst 38h			;296f	ff		.
	rst 38h			;2970	ff		.
	rst 38h			;2971	ff		.
	rst 38h			;2972	ff		.
	rst 38h			;2973	ff		.
	rst 38h			;2974	ff		.
	rst 38h			;2975	ff		.
	rst 38h			;2976	ff		.
	rst 38h			;2977	ff		.
	rst 38h			;2978	ff		.
	rst 38h			;2979	ff		.
	rst 38h			;297a	ff		.
	rst 38h			;297b	ff		.
	rst 38h			;297c	ff		.
	rst 38h			;297d	ff		.
	rst 38h			;297e	ff		.
	rst 38h			;297f	ff		.
	rst 38h			;2980	ff		.
	rst 38h			;2981	ff		.
	rst 38h			;2982	ff		.
	rst 38h			;2983	ff		.
	rst 38h			;2984	ff		.
	rst 38h			;2985	ff		.
	rst 38h			;2986	ff		.
	rst 38h			;2987	ff		.
	rst 38h			;2988	ff		.
	rst 38h			;2989	ff		.
	rst 38h			;298a	ff		.
	rst 38h			;298b	ff		.
	rst 38h			;298c	ff		.
	rst 38h			;298d	ff		.
	rst 38h			;298e	ff		.
	rst 38h			;298f	ff		.
	rst 38h			;2990	ff		.
	rst 38h			;2991	ff		.
	rst 38h			;2992	ff		.
	rst 38h			;2993	ff		.
	rst 38h			;2994	ff		.
	rst 38h			;2995	ff		.
	rst 38h			;2996	ff		.
	rst 38h			;2997	ff		.
	rst 38h			;2998	ff		.
	rst 38h			;2999	ff		.
	rst 38h			;299a	ff		.
	rst 38h			;299b	ff		.
	rst 38h			;299c	ff		.
	rst 38h			;299d	ff		.
	rst 38h			;299e	ff		.
	rst 38h			;299f	ff		.
	rst 38h			;29a0	ff		.
	rst 38h			;29a1	ff		.
	rst 38h			;29a2	ff		.
	rst 38h			;29a3	ff		.
	rst 38h			;29a4	ff		.
	rst 38h			;29a5	ff		.
	rst 38h			;29a6	ff		.
	rst 38h			;29a7	ff		.
	rst 38h			;29a8	ff		.
	rst 38h			;29a9	ff		.
	rst 38h			;29aa	ff		.
	rst 38h			;29ab	ff		.
	rst 38h			;29ac	ff		.
	rst 38h			;29ad	ff		.
	rst 38h			;29ae	ff		.
	rst 38h			;29af	ff		.
	rst 38h			;29b0	ff		.
	rst 38h			;29b1	ff		.
	rst 38h			;29b2	ff		.
	rst 38h			;29b3	ff		.
	rst 38h			;29b4	ff		.
	rst 38h			;29b5	ff		.
	rst 38h			;29b6	ff		.
	rst 38h			;29b7	ff		.
	rst 38h			;29b8	ff		.
	rst 38h			;29b9	ff		.
	rst 38h			;29ba	ff		.
	rst 38h			;29bb	ff		.
	rst 38h			;29bc	ff		.
	rst 38h			;29bd	ff		.
	rst 38h			;29be	ff		.
	rst 38h			;29bf	ff		.
	rst 38h			;29c0	ff		.
	rst 38h			;29c1	ff		.
	rst 38h			;29c2	ff		.
	rst 38h			;29c3	ff		.
	rst 38h			;29c4	ff		.
	rst 38h			;29c5	ff		.
	rst 38h			;29c6	ff		.
	rst 38h			;29c7	ff		.
	rst 38h			;29c8	ff		.
	rst 38h			;29c9	ff		.
	rst 38h			;29ca	ff		.
	rst 38h			;29cb	ff		.
	rst 38h			;29cc	ff		.
	rst 38h			;29cd	ff		.
	rst 38h			;29ce	ff		.
	rst 38h			;29cf	ff		.
	rst 38h			;29d0	ff		.
	rst 38h			;29d1	ff		.
	rst 38h			;29d2	ff		.
	rst 38h			;29d3	ff		.
	rst 38h			;29d4	ff		.
	rst 38h			;29d5	ff		.
	rst 38h			;29d6	ff		.
	rst 38h			;29d7	ff		.
	rst 38h			;29d8	ff		.
	rst 38h			;29d9	ff		.
	rst 38h			;29da	ff		.
	rst 38h			;29db	ff		.
	rst 38h			;29dc	ff		.
	rst 38h			;29dd	ff		.
	rst 38h			;29de	ff		.
	rst 38h			;29df	ff		.
	rst 38h			;29e0	ff		.
	rst 38h			;29e1	ff		.
	rst 38h			;29e2	ff		.
	rst 38h			;29e3	ff		.
	rst 38h			;29e4	ff		.
	rst 38h			;29e5	ff		.
	rst 38h			;29e6	ff		.
	rst 38h			;29e7	ff		.
	rst 38h			;29e8	ff		.
	rst 38h			;29e9	ff		.
	rst 38h			;29ea	ff		.
	rst 38h			;29eb	ff		.
	rst 38h			;29ec	ff		.
	rst 38h			;29ed	ff		.
	rst 38h			;29ee	ff		.
	rst 38h			;29ef	ff		.
	rst 38h			;29f0	ff		.
	rst 38h			;29f1	ff		.
	rst 38h			;29f2	ff		.
	rst 38h			;29f3	ff		.
	rst 38h			;29f4	ff		.
	rst 38h			;29f5	ff		.
	rst 38h			;29f6	ff		.
	rst 38h			;29f7	ff		.
	rst 38h			;29f8	ff		.
	rst 38h			;29f9	ff		.
	rst 38h			;29fa	ff		.
	rst 38h			;29fb	ff		.
	rst 38h			;29fc	ff		.
	rst 38h			;29fd	ff		.
	rst 38h			;29fe	ff		.
	rst 38h			;29ff	ff		.
	rst 38h			;2a00	ff		.
	rst 38h			;2a01	ff		.
	rst 38h			;2a02	ff		.
	rst 38h			;2a03	ff		.
	rst 38h			;2a04	ff		.
	rst 38h			;2a05	ff		.
	rst 38h			;2a06	ff		.
	rst 38h			;2a07	ff		.
	rst 38h			;2a08	ff		.
	rst 38h			;2a09	ff		.
	rst 38h			;2a0a	ff		.
	rst 38h			;2a0b	ff		.
	rst 38h			;2a0c	ff		.
	rst 38h			;2a0d	ff		.
	rst 38h			;2a0e	ff		.
	rst 38h			;2a0f	ff		.
	rst 38h			;2a10	ff		.
	rst 38h			;2a11	ff		.
	rst 38h			;2a12	ff		.
	rst 38h			;2a13	ff		.
	rst 38h			;2a14	ff		.
	rst 38h			;2a15	ff		.
	rst 38h			;2a16	ff		.
	rst 38h			;2a17	ff		.
	rst 38h			;2a18	ff		.
	rst 38h			;2a19	ff		.
	rst 38h			;2a1a	ff		.
	rst 38h			;2a1b	ff		.
	rst 38h			;2a1c	ff		.
	rst 38h			;2a1d	ff		.
	rst 38h			;2a1e	ff		.
	rst 38h			;2a1f	ff		.
	rst 38h			;2a20	ff		.
	rst 38h			;2a21	ff		.
	rst 38h			;2a22	ff		.
	rst 38h			;2a23	ff		.
	rst 38h			;2a24	ff		.
	rst 38h			;2a25	ff		.
	rst 38h			;2a26	ff		.
	rst 38h			;2a27	ff		.
	rst 38h			;2a28	ff		.
	rst 38h			;2a29	ff		.
	rst 38h			;2a2a	ff		.
	rst 38h			;2a2b	ff		.
	rst 38h			;2a2c	ff		.
	rst 38h			;2a2d	ff		.
	rst 38h			;2a2e	ff		.
	rst 38h			;2a2f	ff		.
	rst 38h			;2a30	ff		.
	rst 38h			;2a31	ff		.
	rst 38h			;2a32	ff		.
	rst 38h			;2a33	ff		.
	rst 38h			;2a34	ff		.
	rst 38h			;2a35	ff		.
	rst 38h			;2a36	ff		.
	rst 38h			;2a37	ff		.
	rst 38h			;2a38	ff		.
	rst 38h			;2a39	ff		.
	rst 38h			;2a3a	ff		.
	rst 38h			;2a3b	ff		.
	rst 38h			;2a3c	ff		.
	rst 38h			;2a3d	ff		.
	rst 38h			;2a3e	ff		.
	rst 38h			;2a3f	ff		.
	rst 38h			;2a40	ff		.
	rst 38h			;2a41	ff		.
	rst 38h			;2a42	ff		.
	rst 38h			;2a43	ff		.
	rst 38h			;2a44	ff		.
	rst 38h			;2a45	ff		.
	rst 38h			;2a46	ff		.
	rst 38h			;2a47	ff		.
	rst 38h			;2a48	ff		.
	rst 38h			;2a49	ff		.
	rst 38h			;2a4a	ff		.
	rst 38h			;2a4b	ff		.
	rst 38h			;2a4c	ff		.
	rst 38h			;2a4d	ff		.
	rst 38h			;2a4e	ff		.
	rst 38h			;2a4f	ff		.
	rst 38h			;2a50	ff		.
	rst 38h			;2a51	ff		.
	rst 38h			;2a52	ff		.
	rst 38h			;2a53	ff		.
	rst 38h			;2a54	ff		.
	rst 38h			;2a55	ff		.
	rst 38h			;2a56	ff		.
	rst 38h			;2a57	ff		.
	rst 38h			;2a58	ff		.
	rst 38h			;2a59	ff		.
	rst 38h			;2a5a	ff		.
	rst 38h			;2a5b	ff		.
	rst 38h			;2a5c	ff		.
	rst 38h			;2a5d	ff		.
	rst 38h			;2a5e	ff		.
	rst 38h			;2a5f	ff		.
	rst 38h			;2a60	ff		.
	rst 38h			;2a61	ff		.
	rst 38h			;2a62	ff		.
	rst 38h			;2a63	ff		.
	rst 38h			;2a64	ff		.
	rst 38h			;2a65	ff		.
	rst 38h			;2a66	ff		.
	rst 38h			;2a67	ff		.
	rst 38h			;2a68	ff		.
	rst 38h			;2a69	ff		.
	rst 38h			;2a6a	ff		.
	rst 38h			;2a6b	ff		.
	rst 38h			;2a6c	ff		.
	rst 38h			;2a6d	ff		.
	rst 38h			;2a6e	ff		.
	rst 38h			;2a6f	ff		.
	rst 38h			;2a70	ff		.
	rst 38h			;2a71	ff		.
	rst 38h			;2a72	ff		.
	rst 38h			;2a73	ff		.
	rst 38h			;2a74	ff		.
	rst 38h			;2a75	ff		.
	rst 38h			;2a76	ff		.
	rst 38h			;2a77	ff		.
	rst 38h			;2a78	ff		.
	rst 38h			;2a79	ff		.
	rst 38h			;2a7a	ff		.
	rst 38h			;2a7b	ff		.
	rst 38h			;2a7c	ff		.
	rst 38h			;2a7d	ff		.
	rst 38h			;2a7e	ff		.
	rst 38h			;2a7f	ff		.
	rst 38h			;2a80	ff		.
	rst 38h			;2a81	ff		.
	rst 38h			;2a82	ff		.
	rst 38h			;2a83	ff		.
	rst 38h			;2a84	ff		.
	rst 38h			;2a85	ff		.
	rst 38h			;2a86	ff		.
	rst 38h			;2a87	ff		.
	rst 38h			;2a88	ff		.
	rst 38h			;2a89	ff		.
	rst 38h			;2a8a	ff		.
	rst 38h			;2a8b	ff		.
	rst 38h			;2a8c	ff		.
	rst 38h			;2a8d	ff		.
	rst 38h			;2a8e	ff		.
	rst 38h			;2a8f	ff		.
	rst 38h			;2a90	ff		.
	rst 38h			;2a91	ff		.
	rst 38h			;2a92	ff		.
	rst 38h			;2a93	ff		.
	rst 38h			;2a94	ff		.
	rst 38h			;2a95	ff		.
	rst 38h			;2a96	ff		.
	rst 38h			;2a97	ff		.
	rst 38h			;2a98	ff		.
	rst 38h			;2a99	ff		.
	rst 38h			;2a9a	ff		.
	rst 38h			;2a9b	ff		.
	rst 38h			;2a9c	ff		.
	rst 38h			;2a9d	ff		.
	rst 38h			;2a9e	ff		.
	rst 38h			;2a9f	ff		.
	rst 38h			;2aa0	ff		.
	rst 38h			;2aa1	ff		.
	rst 38h			;2aa2	ff		.
	rst 38h			;2aa3	ff		.
	rst 38h			;2aa4	ff		.
	rst 38h			;2aa5	ff		.
	rst 38h			;2aa6	ff		.
	rst 38h			;2aa7	ff		.
	rst 38h			;2aa8	ff		.
	rst 38h			;2aa9	ff		.
	rst 38h			;2aaa	ff		.
	rst 38h			;2aab	ff		.
	rst 38h			;2aac	ff		.
	rst 38h			;2aad	ff		.
	rst 38h			;2aae	ff		.
	rst 38h			;2aaf	ff		.
	rst 38h			;2ab0	ff		.
	rst 38h			;2ab1	ff		.
	rst 38h			;2ab2	ff		.
	rst 38h			;2ab3	ff		.
	rst 38h			;2ab4	ff		.
	rst 38h			;2ab5	ff		.
	rst 38h			;2ab6	ff		.
	rst 38h			;2ab7	ff		.
	rst 38h			;2ab8	ff		.
	rst 38h			;2ab9	ff		.
	rst 38h			;2aba	ff		.
	rst 38h			;2abb	ff		.
	rst 38h			;2abc	ff		.
	rst 38h			;2abd	ff		.
	rst 38h			;2abe	ff		.
	rst 38h			;2abf	ff		.
	rst 38h			;2ac0	ff		.
	rst 38h			;2ac1	ff		.
	rst 38h			;2ac2	ff		.
	rst 38h			;2ac3	ff		.
	rst 38h			;2ac4	ff		.
	rst 38h			;2ac5	ff		.
	rst 38h			;2ac6	ff		.
	rst 38h			;2ac7	ff		.
	rst 38h			;2ac8	ff		.
	rst 38h			;2ac9	ff		.
	rst 38h			;2aca	ff		.
	rst 38h			;2acb	ff		.
	rst 38h			;2acc	ff		.
	rst 38h			;2acd	ff		.
	rst 38h			;2ace	ff		.
	rst 38h			;2acf	ff		.
	rst 38h			;2ad0	ff		.
	rst 38h			;2ad1	ff		.
	rst 38h			;2ad2	ff		.
	rst 38h			;2ad3	ff		.
	rst 38h			;2ad4	ff		.
	rst 38h			;2ad5	ff		.
	rst 38h			;2ad6	ff		.
	rst 38h			;2ad7	ff		.
	rst 38h			;2ad8	ff		.
	rst 38h			;2ad9	ff		.
	rst 38h			;2ada	ff		.
	rst 38h			;2adb	ff		.
	rst 38h			;2adc	ff		.
	rst 38h			;2add	ff		.
	rst 38h			;2ade	ff		.
	rst 38h			;2adf	ff		.
	rst 38h			;2ae0	ff		.
	rst 38h			;2ae1	ff		.
	rst 38h			;2ae2	ff		.
	rst 38h			;2ae3	ff		.
	rst 38h			;2ae4	ff		.
	rst 38h			;2ae5	ff		.
	rst 38h			;2ae6	ff		.
	rst 38h			;2ae7	ff		.
	rst 38h			;2ae8	ff		.
	rst 38h			;2ae9	ff		.
	rst 38h			;2aea	ff		.
	rst 38h			;2aeb	ff		.
	rst 38h			;2aec	ff		.
	rst 38h			;2aed	ff		.
	rst 38h			;2aee	ff		.
	rst 38h			;2aef	ff		.
	rst 38h			;2af0	ff		.
	rst 38h			;2af1	ff		.
	rst 38h			;2af2	ff		.
	rst 38h			;2af3	ff		.
	rst 38h			;2af4	ff		.
	rst 38h			;2af5	ff		.
	rst 38h			;2af6	ff		.
	rst 38h			;2af7	ff		.
	rst 38h			;2af8	ff		.
	rst 38h			;2af9	ff		.
	rst 38h			;2afa	ff		.
	rst 38h			;2afb	ff		.
	rst 38h			;2afc	ff		.
	rst 38h			;2afd	ff		.
	rst 38h			;2afe	ff		.
	rst 38h			;2aff	ff		.
	rst 38h			;2b00	ff		.
	rst 38h			;2b01	ff		.
	rst 38h			;2b02	ff		.
	rst 38h			;2b03	ff		.
	rst 38h			;2b04	ff		.
	rst 38h			;2b05	ff		.
	rst 38h			;2b06	ff		.
	rst 38h			;2b07	ff		.
	rst 38h			;2b08	ff		.
	rst 38h			;2b09	ff		.
	rst 38h			;2b0a	ff		.
	rst 38h			;2b0b	ff		.
	rst 38h			;2b0c	ff		.
	rst 38h			;2b0d	ff		.
	rst 38h			;2b0e	ff		.
	rst 38h			;2b0f	ff		.
	rst 38h			;2b10	ff		.
	rst 38h			;2b11	ff		.
	rst 38h			;2b12	ff		.
	rst 38h			;2b13	ff		.
	rst 38h			;2b14	ff		.
	rst 38h			;2b15	ff		.
	rst 38h			;2b16	ff		.
	rst 38h			;2b17	ff		.
	rst 38h			;2b18	ff		.
	rst 38h			;2b19	ff		.
	rst 38h			;2b1a	ff		.
	rst 38h			;2b1b	ff		.
	rst 38h			;2b1c	ff		.
	rst 38h			;2b1d	ff		.
	rst 38h			;2b1e	ff		.
	rst 38h			;2b1f	ff		.
	rst 38h			;2b20	ff		.
	rst 38h			;2b21	ff		.
	rst 38h			;2b22	ff		.
	rst 38h			;2b23	ff		.
	rst 38h			;2b24	ff		.
	rst 38h			;2b25	ff		.
	rst 38h			;2b26	ff		.
	rst 38h			;2b27	ff		.
	rst 38h			;2b28	ff		.
	rst 38h			;2b29	ff		.
	rst 38h			;2b2a	ff		.
	rst 38h			;2b2b	ff		.
	rst 38h			;2b2c	ff		.
	rst 38h			;2b2d	ff		.
	rst 38h			;2b2e	ff		.
	rst 38h			;2b2f	ff		.
	rst 38h			;2b30	ff		.
	rst 38h			;2b31	ff		.
	rst 38h			;2b32	ff		.
	rst 38h			;2b33	ff		.
	rst 38h			;2b34	ff		.
	rst 38h			;2b35	ff		.
	rst 38h			;2b36	ff		.
	rst 38h			;2b37	ff		.
	rst 38h			;2b38	ff		.
	rst 38h			;2b39	ff		.
	rst 38h			;2b3a	ff		.
	rst 38h			;2b3b	ff		.
	rst 38h			;2b3c	ff		.
	rst 38h			;2b3d	ff		.
	rst 38h			;2b3e	ff		.
	rst 38h			;2b3f	ff		.
	rst 38h			;2b40	ff		.
	rst 38h			;2b41	ff		.
	rst 38h			;2b42	ff		.
	rst 38h			;2b43	ff		.
	rst 38h			;2b44	ff		.
	rst 38h			;2b45	ff		.
	rst 38h			;2b46	ff		.
	rst 38h			;2b47	ff		.
	rst 38h			;2b48	ff		.
	rst 38h			;2b49	ff		.
	rst 38h			;2b4a	ff		.
	rst 38h			;2b4b	ff		.
	rst 38h			;2b4c	ff		.
	rst 38h			;2b4d	ff		.
	rst 38h			;2b4e	ff		.
	rst 38h			;2b4f	ff		.
	rst 38h			;2b50	ff		.
	rst 38h			;2b51	ff		.
	rst 38h			;2b52	ff		.
	rst 38h			;2b53	ff		.
	rst 38h			;2b54	ff		.
	rst 38h			;2b55	ff		.
	rst 38h			;2b56	ff		.
	rst 38h			;2b57	ff		.
	rst 38h			;2b58	ff		.
	rst 38h			;2b59	ff		.
	rst 38h			;2b5a	ff		.
	rst 38h			;2b5b	ff		.
	rst 38h			;2b5c	ff		.
	rst 38h			;2b5d	ff		.
	rst 38h			;2b5e	ff		.
	rst 38h			;2b5f	ff		.
	rst 38h			;2b60	ff		.
	rst 38h			;2b61	ff		.
	rst 38h			;2b62	ff		.
	rst 38h			;2b63	ff		.
	rst 38h			;2b64	ff		.
	rst 38h			;2b65	ff		.
	rst 38h			;2b66	ff		.
	rst 38h			;2b67	ff		.
	rst 38h			;2b68	ff		.
	rst 38h			;2b69	ff		.
	rst 38h			;2b6a	ff		.
	rst 38h			;2b6b	ff		.
	rst 38h			;2b6c	ff		.
	rst 38h			;2b6d	ff		.
	rst 38h			;2b6e	ff		.
	rst 38h			;2b6f	ff		.
	rst 38h			;2b70	ff		.
	rst 38h			;2b71	ff		.
	rst 38h			;2b72	ff		.
	rst 38h			;2b73	ff		.
	rst 38h			;2b74	ff		.
	rst 38h			;2b75	ff		.
	rst 38h			;2b76	ff		.
	rst 38h			;2b77	ff		.
	rst 38h			;2b78	ff		.
	rst 38h			;2b79	ff		.
	rst 38h			;2b7a	ff		.
	rst 38h			;2b7b	ff		.
	rst 38h			;2b7c	ff		.
	rst 38h			;2b7d	ff		.
	rst 38h			;2b7e	ff		.
	rst 38h			;2b7f	ff		.
	rst 38h			;2b80	ff		.
	rst 38h			;2b81	ff		.
	rst 38h			;2b82	ff		.
	rst 38h			;2b83	ff		.
	rst 38h			;2b84	ff		.
	rst 38h			;2b85	ff		.
	rst 38h			;2b86	ff		.
	rst 38h			;2b87	ff		.
	rst 38h			;2b88	ff		.
	rst 38h			;2b89	ff		.
	rst 38h			;2b8a	ff		.
	rst 38h			;2b8b	ff		.
	rst 38h			;2b8c	ff		.
	rst 38h			;2b8d	ff		.
	rst 38h			;2b8e	ff		.
	rst 38h			;2b8f	ff		.
	rst 38h			;2b90	ff		.
	rst 38h			;2b91	ff		.
	rst 38h			;2b92	ff		.
	rst 38h			;2b93	ff		.
	rst 38h			;2b94	ff		.
	rst 38h			;2b95	ff		.
	rst 38h			;2b96	ff		.
	rst 38h			;2b97	ff		.
	rst 38h			;2b98	ff		.
	rst 38h			;2b99	ff		.
	rst 38h			;2b9a	ff		.
	rst 38h			;2b9b	ff		.
	rst 38h			;2b9c	ff		.
	rst 38h			;2b9d	ff		.
	rst 38h			;2b9e	ff		.
	rst 38h			;2b9f	ff		.
	rst 38h			;2ba0	ff		.
	rst 38h			;2ba1	ff		.
	rst 38h			;2ba2	ff		.
	rst 38h			;2ba3	ff		.
	rst 38h			;2ba4	ff		.
	rst 38h			;2ba5	ff		.
	rst 38h			;2ba6	ff		.
	rst 38h			;2ba7	ff		.
	rst 38h			;2ba8	ff		.
	rst 38h			;2ba9	ff		.
	rst 38h			;2baa	ff		.
	rst 38h			;2bab	ff		.
	rst 38h			;2bac	ff		.
	rst 38h			;2bad	ff		.
	rst 38h			;2bae	ff		.
	rst 38h			;2baf	ff		.
	rst 38h			;2bb0	ff		.
	rst 38h			;2bb1	ff		.
	rst 38h			;2bb2	ff		.
	rst 38h			;2bb3	ff		.
	rst 38h			;2bb4	ff		.
	rst 38h			;2bb5	ff		.
	rst 38h			;2bb6	ff		.
	rst 38h			;2bb7	ff		.
	rst 38h			;2bb8	ff		.
	rst 38h			;2bb9	ff		.
	rst 38h			;2bba	ff		.
	rst 38h			;2bbb	ff		.
	rst 38h			;2bbc	ff		.
	rst 38h			;2bbd	ff		.
	rst 38h			;2bbe	ff		.
	rst 38h			;2bbf	ff		.
	rst 38h			;2bc0	ff		.
	rst 38h			;2bc1	ff		.
	rst 38h			;2bc2	ff		.
	rst 38h			;2bc3	ff		.
	rst 38h			;2bc4	ff		.
	rst 38h			;2bc5	ff		.
	rst 38h			;2bc6	ff		.
	rst 38h			;2bc7	ff		.
	rst 38h			;2bc8	ff		.
	rst 38h			;2bc9	ff		.
	rst 38h			;2bca	ff		.
	rst 38h			;2bcb	ff		.
	rst 38h			;2bcc	ff		.
	rst 38h			;2bcd	ff		.
	rst 38h			;2bce	ff		.
	rst 38h			;2bcf	ff		.
	rst 38h			;2bd0	ff		.
	rst 38h			;2bd1	ff		.
	rst 38h			;2bd2	ff		.
	rst 38h			;2bd3	ff		.
	rst 38h			;2bd4	ff		.
	rst 38h			;2bd5	ff		.
	rst 38h			;2bd6	ff		.
	rst 38h			;2bd7	ff		.
	rst 38h			;2bd8	ff		.
	rst 38h			;2bd9	ff		.
	rst 38h			;2bda	ff		.
	rst 38h			;2bdb	ff		.
	rst 38h			;2bdc	ff		.
	rst 38h			;2bdd	ff		.
	rst 38h			;2bde	ff		.
	rst 38h			;2bdf	ff		.
	rst 38h			;2be0	ff		.
	rst 38h			;2be1	ff		.
	rst 38h			;2be2	ff		.
	rst 38h			;2be3	ff		.
	rst 38h			;2be4	ff		.
	rst 38h			;2be5	ff		.
	rst 38h			;2be6	ff		.
	rst 38h			;2be7	ff		.
	rst 38h			;2be8	ff		.
	rst 38h			;2be9	ff		.
	rst 38h			;2bea	ff		.
	rst 38h			;2beb	ff		.
	rst 38h			;2bec	ff		.
	rst 38h			;2bed	ff		.
	rst 38h			;2bee	ff		.
	rst 38h			;2bef	ff		.
	rst 38h			;2bf0	ff		.
	rst 38h			;2bf1	ff		.
	rst 38h			;2bf2	ff		.
	rst 38h			;2bf3	ff		.
	rst 38h			;2bf4	ff		.
	rst 38h			;2bf5	ff		.
	rst 38h			;2bf6	ff		.
	rst 38h			;2bf7	ff		.
	rst 38h			;2bf8	ff		.
	rst 38h			;2bf9	ff		.
	rst 38h			;2bfa	ff		.
	rst 38h			;2bfb	ff		.
	rst 38h			;2bfc	ff		.
	rst 38h			;2bfd	ff		.
	rst 38h			;2bfe	ff		.
	rst 38h			;2bff	ff		.
	rst 38h			;2c00	ff		.
	rst 38h			;2c01	ff		.
	rst 38h			;2c02	ff		.
	rst 38h			;2c03	ff		.
	rst 38h			;2c04	ff		.
	rst 38h			;2c05	ff		.
	rst 38h			;2c06	ff		.
	rst 38h			;2c07	ff		.
	rst 38h			;2c08	ff		.
	rst 38h			;2c09	ff		.
	rst 38h			;2c0a	ff		.
	rst 38h			;2c0b	ff		.
	rst 38h			;2c0c	ff		.
	rst 38h			;2c0d	ff		.
	rst 38h			;2c0e	ff		.
	rst 38h			;2c0f	ff		.
	rst 38h			;2c10	ff		.
	rst 38h			;2c11	ff		.
	rst 38h			;2c12	ff		.
	rst 38h			;2c13	ff		.
	rst 38h			;2c14	ff		.
	rst 38h			;2c15	ff		.
	rst 38h			;2c16	ff		.
	rst 38h			;2c17	ff		.
	rst 38h			;2c18	ff		.
	rst 38h			;2c19	ff		.
	rst 38h			;2c1a	ff		.
	rst 38h			;2c1b	ff		.
	rst 38h			;2c1c	ff		.
	rst 38h			;2c1d	ff		.
	rst 38h			;2c1e	ff		.
	rst 38h			;2c1f	ff		.
	rst 38h			;2c20	ff		.
	rst 38h			;2c21	ff		.
	rst 38h			;2c22	ff		.
	rst 38h			;2c23	ff		.
	rst 38h			;2c24	ff		.
	rst 38h			;2c25	ff		.
	rst 38h			;2c26	ff		.
	rst 38h			;2c27	ff		.
	rst 38h			;2c28	ff		.
	rst 38h			;2c29	ff		.
	rst 38h			;2c2a	ff		.
	rst 38h			;2c2b	ff		.
	rst 38h			;2c2c	ff		.
	rst 38h			;2c2d	ff		.
	rst 38h			;2c2e	ff		.
	rst 38h			;2c2f	ff		.
	rst 38h			;2c30	ff		.
	rst 38h			;2c31	ff		.
	rst 38h			;2c32	ff		.
	rst 38h			;2c33	ff		.
	rst 38h			;2c34	ff		.
	rst 38h			;2c35	ff		.
	rst 38h			;2c36	ff		.
	rst 38h			;2c37	ff		.
	rst 38h			;2c38	ff		.
	rst 38h			;2c39	ff		.
	rst 38h			;2c3a	ff		.
	rst 38h			;2c3b	ff		.
	rst 38h			;2c3c	ff		.
	rst 38h			;2c3d	ff		.
	rst 38h			;2c3e	ff		.
	rst 38h			;2c3f	ff		.
	rst 38h			;2c40	ff		.
	rst 38h			;2c41	ff		.
	rst 38h			;2c42	ff		.
	rst 38h			;2c43	ff		.
	rst 38h			;2c44	ff		.
	rst 38h			;2c45	ff		.
	rst 38h			;2c46	ff		.
	rst 38h			;2c47	ff		.
	rst 38h			;2c48	ff		.
	rst 38h			;2c49	ff		.
	rst 38h			;2c4a	ff		.
	rst 38h			;2c4b	ff		.
	rst 38h			;2c4c	ff		.
	rst 38h			;2c4d	ff		.
	rst 38h			;2c4e	ff		.
	rst 38h			;2c4f	ff		.
	rst 38h			;2c50	ff		.
	rst 38h			;2c51	ff		.
	rst 38h			;2c52	ff		.
	rst 38h			;2c53	ff		.
	rst 38h			;2c54	ff		.
	rst 38h			;2c55	ff		.
	rst 38h			;2c56	ff		.
	rst 38h			;2c57	ff		.
	rst 38h			;2c58	ff		.
	rst 38h			;2c59	ff		.
	rst 38h			;2c5a	ff		.
	rst 38h			;2c5b	ff		.
	rst 38h			;2c5c	ff		.
	rst 38h			;2c5d	ff		.
	rst 38h			;2c5e	ff		.
	rst 38h			;2c5f	ff		.
	rst 38h			;2c60	ff		.
	rst 38h			;2c61	ff		.
	rst 38h			;2c62	ff		.
	rst 38h			;2c63	ff		.
	rst 38h			;2c64	ff		.
	rst 38h			;2c65	ff		.
	rst 38h			;2c66	ff		.
	rst 38h			;2c67	ff		.
	rst 38h			;2c68	ff		.
	rst 38h			;2c69	ff		.
	rst 38h			;2c6a	ff		.
	rst 38h			;2c6b	ff		.
	rst 38h			;2c6c	ff		.
	rst 38h			;2c6d	ff		.
	rst 38h			;2c6e	ff		.
	rst 38h			;2c6f	ff		.
l2c70h:
	rst 38h			;2c70	ff		.
	rst 38h			;2c71	ff		.
	rst 38h			;2c72	ff		.
	rst 38h			;2c73	ff		.
	rst 38h			;2c74	ff		.
	rst 38h			;2c75	ff		.
	rst 38h			;2c76	ff		.
	rst 38h			;2c77	ff		.
	rst 38h			;2c78	ff		.
	rst 38h			;2c79	ff		.
	rst 38h			;2c7a	ff		.
	rst 38h			;2c7b	ff		.
	rst 38h			;2c7c	ff		.
	rst 38h			;2c7d	ff		.
	rst 38h			;2c7e	ff		.
	rst 38h			;2c7f	ff		.
	rst 38h			;2c80	ff		.
	rst 38h			;2c81	ff		.
	rst 38h			;2c82	ff		.
	rst 38h			;2c83	ff		.
	rst 38h			;2c84	ff		.
	rst 38h			;2c85	ff		.
	rst 38h			;2c86	ff		.
	rst 38h			;2c87	ff		.
	rst 38h			;2c88	ff		.
	rst 38h			;2c89	ff		.
	rst 38h			;2c8a	ff		.
	rst 38h			;2c8b	ff		.
	rst 38h			;2c8c	ff		.
	rst 38h			;2c8d	ff		.
	rst 38h			;2c8e	ff		.
	rst 38h			;2c8f	ff		.
	rst 38h			;2c90	ff		.
	rst 38h			;2c91	ff		.
	rst 38h			;2c92	ff		.
	rst 38h			;2c93	ff		.
	rst 38h			;2c94	ff		.
	rst 38h			;2c95	ff		.
	rst 38h			;2c96	ff		.
	rst 38h			;2c97	ff		.
	rst 38h			;2c98	ff		.
	rst 38h			;2c99	ff		.
	rst 38h			;2c9a	ff		.
	rst 38h			;2c9b	ff		.
	rst 38h			;2c9c	ff		.
	rst 38h			;2c9d	ff		.
	rst 38h			;2c9e	ff		.
	rst 38h			;2c9f	ff		.
	rst 38h			;2ca0	ff		.
	rst 38h			;2ca1	ff		.
	rst 38h			;2ca2	ff		.
	rst 38h			;2ca3	ff		.
	rst 38h			;2ca4	ff		.
	rst 38h			;2ca5	ff		.
	rst 38h			;2ca6	ff		.
	rst 38h			;2ca7	ff		.
	rst 38h			;2ca8	ff		.
	rst 38h			;2ca9	ff		.
	rst 38h			;2caa	ff		.
	rst 38h			;2cab	ff		.
	rst 38h			;2cac	ff		.
	rst 38h			;2cad	ff		.
	rst 38h			;2cae	ff		.
	rst 38h			;2caf	ff		.
	rst 38h			;2cb0	ff		.
	rst 38h			;2cb1	ff		.
	rst 38h			;2cb2	ff		.
	rst 38h			;2cb3	ff		.
	rst 38h			;2cb4	ff		.
	rst 38h			;2cb5	ff		.
	rst 38h			;2cb6	ff		.
	rst 38h			;2cb7	ff		.
	rst 38h			;2cb8	ff		.
	rst 38h			;2cb9	ff		.
	rst 38h			;2cba	ff		.
	rst 38h			;2cbb	ff		.
	rst 38h			;2cbc	ff		.
	rst 38h			;2cbd	ff		.
	rst 38h			;2cbe	ff		.
	rst 38h			;2cbf	ff		.
	rst 38h			;2cc0	ff		.
	rst 38h			;2cc1	ff		.
	rst 38h			;2cc2	ff		.
	rst 38h			;2cc3	ff		.
	rst 38h			;2cc4	ff		.
	rst 38h			;2cc5	ff		.
	rst 38h			;2cc6	ff		.
	rst 38h			;2cc7	ff		.
	rst 38h			;2cc8	ff		.
	rst 38h			;2cc9	ff		.
	rst 38h			;2cca	ff		.
	rst 38h			;2ccb	ff		.
	rst 38h			;2ccc	ff		.
	rst 38h			;2ccd	ff		.
	rst 38h			;2cce	ff		.
	rst 38h			;2ccf	ff		.
	rst 38h			;2cd0	ff		.
	rst 38h			;2cd1	ff		.
	rst 38h			;2cd2	ff		.
	rst 38h			;2cd3	ff		.
	rst 38h			;2cd4	ff		.
	rst 38h			;2cd5	ff		.
	rst 38h			;2cd6	ff		.
	rst 38h			;2cd7	ff		.
	rst 38h			;2cd8	ff		.
	rst 38h			;2cd9	ff		.
	rst 38h			;2cda	ff		.
	rst 38h			;2cdb	ff		.
	rst 38h			;2cdc	ff		.
	rst 38h			;2cdd	ff		.
	rst 38h			;2cde	ff		.
	rst 38h			;2cdf	ff		.
	rst 38h			;2ce0	ff		.
	rst 38h			;2ce1	ff		.
	rst 38h			;2ce2	ff		.
	rst 38h			;2ce3	ff		.
	rst 38h			;2ce4	ff		.
	rst 38h			;2ce5	ff		.
	rst 38h			;2ce6	ff		.
	rst 38h			;2ce7	ff		.
	rst 38h			;2ce8	ff		.
	rst 38h			;2ce9	ff		.
	rst 38h			;2cea	ff		.
	rst 38h			;2ceb	ff		.
	rst 38h			;2cec	ff		.
	rst 38h			;2ced	ff		.
	rst 38h			;2cee	ff		.
	rst 38h			;2cef	ff		.
	rst 38h			;2cf0	ff		.
	rst 38h			;2cf1	ff		.
	rst 38h			;2cf2	ff		.
	rst 38h			;2cf3	ff		.
	rst 38h			;2cf4	ff		.
	rst 38h			;2cf5	ff		.
	rst 38h			;2cf6	ff		.
	rst 38h			;2cf7	ff		.
	rst 38h			;2cf8	ff		.
	rst 38h			;2cf9	ff		.
	rst 38h			;2cfa	ff		.
	rst 38h			;2cfb	ff		.
	rst 38h			;2cfc	ff		.
	rst 38h			;2cfd	ff		.
	rst 38h			;2cfe	ff		.
	rst 38h			;2cff	ff		.
	rst 38h			;2d00	ff		.
	rst 38h			;2d01	ff		.
	rst 38h			;2d02	ff		.
	rst 38h			;2d03	ff		.
	rst 38h			;2d04	ff		.
	rst 38h			;2d05	ff		.
	rst 38h			;2d06	ff		.
	rst 38h			;2d07	ff		.
	rst 38h			;2d08	ff		.
	rst 38h			;2d09	ff		.
	rst 38h			;2d0a	ff		.
	rst 38h			;2d0b	ff		.
	rst 38h			;2d0c	ff		.
	rst 38h			;2d0d	ff		.
	rst 38h			;2d0e	ff		.
	rst 38h			;2d0f	ff		.
	rst 38h			;2d10	ff		.
	rst 38h			;2d11	ff		.
	rst 38h			;2d12	ff		.
	rst 38h			;2d13	ff		.
	rst 38h			;2d14	ff		.
	rst 38h			;2d15	ff		.
	rst 38h			;2d16	ff		.
	rst 38h			;2d17	ff		.
	rst 38h			;2d18	ff		.
	rst 38h			;2d19	ff		.
	rst 38h			;2d1a	ff		.
	rst 38h			;2d1b	ff		.
	rst 38h			;2d1c	ff		.
	rst 38h			;2d1d	ff		.
	rst 38h			;2d1e	ff		.
	rst 38h			;2d1f	ff		.
	rst 38h			;2d20	ff		.
	rst 38h			;2d21	ff		.
	rst 38h			;2d22	ff		.
	rst 38h			;2d23	ff		.
	rst 38h			;2d24	ff		.
	rst 38h			;2d25	ff		.
	rst 38h			;2d26	ff		.
	rst 38h			;2d27	ff		.
	rst 38h			;2d28	ff		.
	rst 38h			;2d29	ff		.
	rst 38h			;2d2a	ff		.
	rst 38h			;2d2b	ff		.
	rst 38h			;2d2c	ff		.
	rst 38h			;2d2d	ff		.
	rst 38h			;2d2e	ff		.
	rst 38h			;2d2f	ff		.
	rst 38h			;2d30	ff		.
	rst 38h			;2d31	ff		.
	rst 38h			;2d32	ff		.
	rst 38h			;2d33	ff		.
	rst 38h			;2d34	ff		.
	rst 38h			;2d35	ff		.
	rst 38h			;2d36	ff		.
	rst 38h			;2d37	ff		.
	rst 38h			;2d38	ff		.
	rst 38h			;2d39	ff		.
	rst 38h			;2d3a	ff		.
	rst 38h			;2d3b	ff		.
	rst 38h			;2d3c	ff		.
	rst 38h			;2d3d	ff		.
	rst 38h			;2d3e	ff		.
	rst 38h			;2d3f	ff		.
	rst 38h			;2d40	ff		.
	rst 38h			;2d41	ff		.
	rst 38h			;2d42	ff		.
	rst 38h			;2d43	ff		.
	rst 38h			;2d44	ff		.
	rst 38h			;2d45	ff		.
	rst 38h			;2d46	ff		.
	rst 38h			;2d47	ff		.
	rst 38h			;2d48	ff		.
	rst 38h			;2d49	ff		.
	rst 38h			;2d4a	ff		.
	rst 38h			;2d4b	ff		.
	rst 38h			;2d4c	ff		.
	rst 38h			;2d4d	ff		.
	rst 38h			;2d4e	ff		.
	rst 38h			;2d4f	ff		.
	rst 38h			;2d50	ff		.
	rst 38h			;2d51	ff		.
	rst 38h			;2d52	ff		.
	rst 38h			;2d53	ff		.
	rst 38h			;2d54	ff		.
	rst 38h			;2d55	ff		.
	rst 38h			;2d56	ff		.
	rst 38h			;2d57	ff		.
	rst 38h			;2d58	ff		.
	rst 38h			;2d59	ff		.
	rst 38h			;2d5a	ff		.
	rst 38h			;2d5b	ff		.
	rst 38h			;2d5c	ff		.
	rst 38h			;2d5d	ff		.
	rst 38h			;2d5e	ff		.
	rst 38h			;2d5f	ff		.
	rst 38h			;2d60	ff		.
	rst 38h			;2d61	ff		.
	rst 38h			;2d62	ff		.
	rst 38h			;2d63	ff		.
	rst 38h			;2d64	ff		.
	rst 38h			;2d65	ff		.
	rst 38h			;2d66	ff		.
	rst 38h			;2d67	ff		.
	rst 38h			;2d68	ff		.
	rst 38h			;2d69	ff		.
	rst 38h			;2d6a	ff		.
	rst 38h			;2d6b	ff		.
	rst 38h			;2d6c	ff		.
	rst 38h			;2d6d	ff		.
	rst 38h			;2d6e	ff		.
	rst 38h			;2d6f	ff		.
	rst 38h			;2d70	ff		.
	rst 38h			;2d71	ff		.
	rst 38h			;2d72	ff		.
	rst 38h			;2d73	ff		.
	rst 38h			;2d74	ff		.
	rst 38h			;2d75	ff		.
	rst 38h			;2d76	ff		.
	rst 38h			;2d77	ff		.
	rst 38h			;2d78	ff		.
	rst 38h			;2d79	ff		.
	rst 38h			;2d7a	ff		.
	rst 38h			;2d7b	ff		.
	rst 38h			;2d7c	ff		.
	rst 38h			;2d7d	ff		.
	rst 38h			;2d7e	ff		.
	rst 38h			;2d7f	ff		.
	rst 38h			;2d80	ff		.
	rst 38h			;2d81	ff		.
	rst 38h			;2d82	ff		.
	rst 38h			;2d83	ff		.
	rst 38h			;2d84	ff		.
	rst 38h			;2d85	ff		.
	rst 38h			;2d86	ff		.
	rst 38h			;2d87	ff		.
	rst 38h			;2d88	ff		.
	rst 38h			;2d89	ff		.
	rst 38h			;2d8a	ff		.
	rst 38h			;2d8b	ff		.
	rst 38h			;2d8c	ff		.
	rst 38h			;2d8d	ff		.
	rst 38h			;2d8e	ff		.
	rst 38h			;2d8f	ff		.
	rst 38h			;2d90	ff		.
	rst 38h			;2d91	ff		.
	rst 38h			;2d92	ff		.
	rst 38h			;2d93	ff		.
	rst 38h			;2d94	ff		.
	rst 38h			;2d95	ff		.
	rst 38h			;2d96	ff		.
	rst 38h			;2d97	ff		.
	rst 38h			;2d98	ff		.
	rst 38h			;2d99	ff		.
	rst 38h			;2d9a	ff		.
	rst 38h			;2d9b	ff		.
	rst 38h			;2d9c	ff		.
	rst 38h			;2d9d	ff		.
	rst 38h			;2d9e	ff		.
	rst 38h			;2d9f	ff		.
	rst 38h			;2da0	ff		.
	rst 38h			;2da1	ff		.
	rst 38h			;2da2	ff		.
	rst 38h			;2da3	ff		.
	rst 38h			;2da4	ff		.
	rst 38h			;2da5	ff		.
	rst 38h			;2da6	ff		.
	rst 38h			;2da7	ff		.
	rst 38h			;2da8	ff		.
	rst 38h			;2da9	ff		.
	rst 38h			;2daa	ff		.
	rst 38h			;2dab	ff		.
	rst 38h			;2dac	ff		.
	rst 38h			;2dad	ff		.
	rst 38h			;2dae	ff		.
	rst 38h			;2daf	ff		.
	rst 38h			;2db0	ff		.
	rst 38h			;2db1	ff		.
	rst 38h			;2db2	ff		.
	rst 38h			;2db3	ff		.
	rst 38h			;2db4	ff		.
	rst 38h			;2db5	ff		.
	rst 38h			;2db6	ff		.
	rst 38h			;2db7	ff		.
	rst 38h			;2db8	ff		.
	rst 38h			;2db9	ff		.
	rst 38h			;2dba	ff		.
	rst 38h			;2dbb	ff		.
	rst 38h			;2dbc	ff		.
	rst 38h			;2dbd	ff		.
	rst 38h			;2dbe	ff		.
	rst 38h			;2dbf	ff		.
	rst 38h			;2dc0	ff		.
	rst 38h			;2dc1	ff		.
	rst 38h			;2dc2	ff		.
	rst 38h			;2dc3	ff		.
	rst 38h			;2dc4	ff		.
	rst 38h			;2dc5	ff		.
	rst 38h			;2dc6	ff		.
	rst 38h			;2dc7	ff		.
	rst 38h			;2dc8	ff		.
	rst 38h			;2dc9	ff		.
	rst 38h			;2dca	ff		.
	rst 38h			;2dcb	ff		.
	rst 38h			;2dcc	ff		.
	rst 38h			;2dcd	ff		.
	rst 38h			;2dce	ff		.
	rst 38h			;2dcf	ff		.
	rst 38h			;2dd0	ff		.
	rst 38h			;2dd1	ff		.
	rst 38h			;2dd2	ff		.
	rst 38h			;2dd3	ff		.
	rst 38h			;2dd4	ff		.
	rst 38h			;2dd5	ff		.
	rst 38h			;2dd6	ff		.
	rst 38h			;2dd7	ff		.
	rst 38h			;2dd8	ff		.
	rst 38h			;2dd9	ff		.
	rst 38h			;2dda	ff		.
	rst 38h			;2ddb	ff		.
	rst 38h			;2ddc	ff		.
	rst 38h			;2ddd	ff		.
	rst 38h			;2dde	ff		.
	rst 38h			;2ddf	ff		.
	rst 38h			;2de0	ff		.
	rst 38h			;2de1	ff		.
	rst 38h			;2de2	ff		.
	rst 38h			;2de3	ff		.
	rst 38h			;2de4	ff		.
	rst 38h			;2de5	ff		.
	rst 38h			;2de6	ff		.
	rst 38h			;2de7	ff		.
	rst 38h			;2de8	ff		.
	rst 38h			;2de9	ff		.
	rst 38h			;2dea	ff		.
	rst 38h			;2deb	ff		.
	rst 38h			;2dec	ff		.
	rst 38h			;2ded	ff		.
	rst 38h			;2dee	ff		.
	rst 38h			;2def	ff		.
	rst 38h			;2df0	ff		.
	rst 38h			;2df1	ff		.
	rst 38h			;2df2	ff		.
	rst 38h			;2df3	ff		.
	rst 38h			;2df4	ff		.
	rst 38h			;2df5	ff		.
	rst 38h			;2df6	ff		.
	rst 38h			;2df7	ff		.
	rst 38h			;2df8	ff		.
	rst 38h			;2df9	ff		.
	rst 38h			;2dfa	ff		.
	rst 38h			;2dfb	ff		.
	rst 38h			;2dfc	ff		.
	rst 38h			;2dfd	ff		.
	rst 38h			;2dfe	ff		.
	rst 38h			;2dff	ff		.
	rst 38h			;2e00	ff		.
	rst 38h			;2e01	ff		.
	rst 38h			;2e02	ff		.
	rst 38h			;2e03	ff		.
	rst 38h			;2e04	ff		.
	rst 38h			;2e05	ff		.
	rst 38h			;2e06	ff		.
	rst 38h			;2e07	ff		.
	rst 38h			;2e08	ff		.
	rst 38h			;2e09	ff		.
	rst 38h			;2e0a	ff		.
	rst 38h			;2e0b	ff		.
	rst 38h			;2e0c	ff		.
	rst 38h			;2e0d	ff		.
	rst 38h			;2e0e	ff		.
	rst 38h			;2e0f	ff		.
	rst 38h			;2e10	ff		.
	rst 38h			;2e11	ff		.
	rst 38h			;2e12	ff		.
	rst 38h			;2e13	ff		.
	rst 38h			;2e14	ff		.
	rst 38h			;2e15	ff		.
	rst 38h			;2e16	ff		.
	rst 38h			;2e17	ff		.
	rst 38h			;2e18	ff		.
	rst 38h			;2e19	ff		.
	rst 38h			;2e1a	ff		.
	rst 38h			;2e1b	ff		.
	rst 38h			;2e1c	ff		.
	rst 38h			;2e1d	ff		.
	rst 38h			;2e1e	ff		.
	rst 38h			;2e1f	ff		.
	rst 38h			;2e20	ff		.
	rst 38h			;2e21	ff		.
	rst 38h			;2e22	ff		.
	rst 38h			;2e23	ff		.
	rst 38h			;2e24	ff		.
	rst 38h			;2e25	ff		.
	rst 38h			;2e26	ff		.
	rst 38h			;2e27	ff		.
	rst 38h			;2e28	ff		.
	rst 38h			;2e29	ff		.
	rst 38h			;2e2a	ff		.
	rst 38h			;2e2b	ff		.
	rst 38h			;2e2c	ff		.
	rst 38h			;2e2d	ff		.
	rst 38h			;2e2e	ff		.
	rst 38h			;2e2f	ff		.
	rst 38h			;2e30	ff		.
	rst 38h			;2e31	ff		.
	rst 38h			;2e32	ff		.
	rst 38h			;2e33	ff		.
	rst 38h			;2e34	ff		.
	rst 38h			;2e35	ff		.
	rst 38h			;2e36	ff		.
	rst 38h			;2e37	ff		.
	rst 38h			;2e38	ff		.
	rst 38h			;2e39	ff		.
	rst 38h			;2e3a	ff		.
	rst 38h			;2e3b	ff		.
	rst 38h			;2e3c	ff		.
	rst 38h			;2e3d	ff		.
	rst 38h			;2e3e	ff		.
	rst 38h			;2e3f	ff		.
	rst 38h			;2e40	ff		.
	rst 38h			;2e41	ff		.
	rst 38h			;2e42	ff		.
	rst 38h			;2e43	ff		.
	rst 38h			;2e44	ff		.
	rst 38h			;2e45	ff		.
	rst 38h			;2e46	ff		.
	rst 38h			;2e47	ff		.
	rst 38h			;2e48	ff		.
	rst 38h			;2e49	ff		.
	rst 38h			;2e4a	ff		.
	rst 38h			;2e4b	ff		.
	rst 38h			;2e4c	ff		.
	rst 38h			;2e4d	ff		.
	rst 38h			;2e4e	ff		.
	rst 38h			;2e4f	ff		.
	rst 38h			;2e50	ff		.
	rst 38h			;2e51	ff		.
	rst 38h			;2e52	ff		.
	rst 38h			;2e53	ff		.
	rst 38h			;2e54	ff		.
	rst 38h			;2e55	ff		.
	rst 38h			;2e56	ff		.
	rst 38h			;2e57	ff		.
	rst 38h			;2e58	ff		.
	rst 38h			;2e59	ff		.
	rst 38h			;2e5a	ff		.
	rst 38h			;2e5b	ff		.
	rst 38h			;2e5c	ff		.
	rst 38h			;2e5d	ff		.
	rst 38h			;2e5e	ff		.
	rst 38h			;2e5f	ff		.
	rst 38h			;2e60	ff		.
	rst 38h			;2e61	ff		.
	rst 38h			;2e62	ff		.
	rst 38h			;2e63	ff		.
	rst 38h			;2e64	ff		.
	rst 38h			;2e65	ff		.
	rst 38h			;2e66	ff		.
	rst 38h			;2e67	ff		.
	rst 38h			;2e68	ff		.
	rst 38h			;2e69	ff		.
	rst 38h			;2e6a	ff		.
	rst 38h			;2e6b	ff		.
	rst 38h			;2e6c	ff		.
	rst 38h			;2e6d	ff		.
	rst 38h			;2e6e	ff		.
	rst 38h			;2e6f	ff		.
	rst 38h			;2e70	ff		.
	rst 38h			;2e71	ff		.
	rst 38h			;2e72	ff		.
	rst 38h			;2e73	ff		.
	rst 38h			;2e74	ff		.
	rst 38h			;2e75	ff		.
	rst 38h			;2e76	ff		.
	rst 38h			;2e77	ff		.
	rst 38h			;2e78	ff		.
	rst 38h			;2e79	ff		.
	rst 38h			;2e7a	ff		.
	rst 38h			;2e7b	ff		.
	rst 38h			;2e7c	ff		.
	rst 38h			;2e7d	ff		.
	rst 38h			;2e7e	ff		.
	rst 38h			;2e7f	ff		.
	rst 38h			;2e80	ff		.
	rst 38h			;2e81	ff		.
	rst 38h			;2e82	ff		.
	rst 38h			;2e83	ff		.
	rst 38h			;2e84	ff		.
	rst 38h			;2e85	ff		.
	rst 38h			;2e86	ff		.
	rst 38h			;2e87	ff		.
	rst 38h			;2e88	ff		.
	rst 38h			;2e89	ff		.
	rst 38h			;2e8a	ff		.
	rst 38h			;2e8b	ff		.
	rst 38h			;2e8c	ff		.
	rst 38h			;2e8d	ff		.
	rst 38h			;2e8e	ff		.
	rst 38h			;2e8f	ff		.
	rst 38h			;2e90	ff		.
	rst 38h			;2e91	ff		.
	rst 38h			;2e92	ff		.
	rst 38h			;2e93	ff		.
	rst 38h			;2e94	ff		.
	rst 38h			;2e95	ff		.
	rst 38h			;2e96	ff		.
	rst 38h			;2e97	ff		.
	rst 38h			;2e98	ff		.
	rst 38h			;2e99	ff		.
	rst 38h			;2e9a	ff		.
	rst 38h			;2e9b	ff		.
	rst 38h			;2e9c	ff		.
	rst 38h			;2e9d	ff		.
	rst 38h			;2e9e	ff		.
	rst 38h			;2e9f	ff		.
	rst 38h			;2ea0	ff		.
	rst 38h			;2ea1	ff		.
	rst 38h			;2ea2	ff		.
	rst 38h			;2ea3	ff		.
	rst 38h			;2ea4	ff		.
	rst 38h			;2ea5	ff		.
	rst 38h			;2ea6	ff		.
	rst 38h			;2ea7	ff		.
	rst 38h			;2ea8	ff		.
	rst 38h			;2ea9	ff		.
	rst 38h			;2eaa	ff		.
	rst 38h			;2eab	ff		.
	rst 38h			;2eac	ff		.
	rst 38h			;2ead	ff		.
	rst 38h			;2eae	ff		.
	rst 38h			;2eaf	ff		.
	rst 38h			;2eb0	ff		.
	rst 38h			;2eb1	ff		.
	rst 38h			;2eb2	ff		.
	rst 38h			;2eb3	ff		.
	rst 38h			;2eb4	ff		.
	rst 38h			;2eb5	ff		.
	rst 38h			;2eb6	ff		.
	rst 38h			;2eb7	ff		.
	rst 38h			;2eb8	ff		.
	rst 38h			;2eb9	ff		.
	rst 38h			;2eba	ff		.
	rst 38h			;2ebb	ff		.
	rst 38h			;2ebc	ff		.
	rst 38h			;2ebd	ff		.
	rst 38h			;2ebe	ff		.
	rst 38h			;2ebf	ff		.
	rst 38h			;2ec0	ff		.
	rst 38h			;2ec1	ff		.
	rst 38h			;2ec2	ff		.
	rst 38h			;2ec3	ff		.
	rst 38h			;2ec4	ff		.
	rst 38h			;2ec5	ff		.
	rst 38h			;2ec6	ff		.
	rst 38h			;2ec7	ff		.
	rst 38h			;2ec8	ff		.
	rst 38h			;2ec9	ff		.
	rst 38h			;2eca	ff		.
	rst 38h			;2ecb	ff		.
	rst 38h			;2ecc	ff		.
	rst 38h			;2ecd	ff		.
	rst 38h			;2ece	ff		.
	rst 38h			;2ecf	ff		.
	rst 38h			;2ed0	ff		.
	rst 38h			;2ed1	ff		.
	rst 38h			;2ed2	ff		.
	rst 38h			;2ed3	ff		.
	rst 38h			;2ed4	ff		.
	rst 38h			;2ed5	ff		.
	rst 38h			;2ed6	ff		.
	rst 38h			;2ed7	ff		.
	rst 38h			;2ed8	ff		.
	rst 38h			;2ed9	ff		.
	rst 38h			;2eda	ff		.
	rst 38h			;2edb	ff		.
	rst 38h			;2edc	ff		.
	rst 38h			;2edd	ff		.
	rst 38h			;2ede	ff		.
	rst 38h			;2edf	ff		.
	rst 38h			;2ee0	ff		.
	rst 38h			;2ee1	ff		.
	rst 38h			;2ee2	ff		.
	rst 38h			;2ee3	ff		.
	rst 38h			;2ee4	ff		.
	rst 38h			;2ee5	ff		.
	rst 38h			;2ee6	ff		.
	rst 38h			;2ee7	ff		.
	rst 38h			;2ee8	ff		.
	rst 38h			;2ee9	ff		.
	rst 38h			;2eea	ff		.
	rst 38h			;2eeb	ff		.
	rst 38h			;2eec	ff		.
	rst 38h			;2eed	ff		.
	rst 38h			;2eee	ff		.
	rst 38h			;2eef	ff		.
	rst 38h			;2ef0	ff		.
	rst 38h			;2ef1	ff		.
	rst 38h			;2ef2	ff		.
	rst 38h			;2ef3	ff		.
	rst 38h			;2ef4	ff		.
	rst 38h			;2ef5	ff		.
	rst 38h			;2ef6	ff		.
	rst 38h			;2ef7	ff		.
	rst 38h			;2ef8	ff		.
	rst 38h			;2ef9	ff		.
	rst 38h			;2efa	ff		.
	rst 38h			;2efb	ff		.
	rst 38h			;2efc	ff		.
	rst 38h			;2efd	ff		.
	rst 38h			;2efe	ff		.
	rst 38h			;2eff	ff		.
	rst 38h			;2f00	ff		.
	rst 38h			;2f01	ff		.
	rst 38h			;2f02	ff		.
	rst 38h			;2f03	ff		.
	rst 38h			;2f04	ff		.
	rst 38h			;2f05	ff		.
	rst 38h			;2f06	ff		.
	rst 38h			;2f07	ff		.
	rst 38h			;2f08	ff		.
	rst 38h			;2f09	ff		.
	rst 38h			;2f0a	ff		.
	rst 38h			;2f0b	ff		.
	rst 38h			;2f0c	ff		.
	rst 38h			;2f0d	ff		.
	rst 38h			;2f0e	ff		.
	rst 38h			;2f0f	ff		.
	rst 38h			;2f10	ff		.
	rst 38h			;2f11	ff		.
	rst 38h			;2f12	ff		.
	rst 38h			;2f13	ff		.
	rst 38h			;2f14	ff		.
	rst 38h			;2f15	ff		.
	rst 38h			;2f16	ff		.
	rst 38h			;2f17	ff		.
	rst 38h			;2f18	ff		.
	rst 38h			;2f19	ff		.
	rst 38h			;2f1a	ff		.
	rst 38h			;2f1b	ff		.
	rst 38h			;2f1c	ff		.
	rst 38h			;2f1d	ff		.
	rst 38h			;2f1e	ff		.
	rst 38h			;2f1f	ff		.
	rst 38h			;2f20	ff		.
	rst 38h			;2f21	ff		.
	rst 38h			;2f22	ff		.
	rst 38h			;2f23	ff		.
	rst 38h			;2f24	ff		.
	rst 38h			;2f25	ff		.
	rst 38h			;2f26	ff		.
	rst 38h			;2f27	ff		.
	rst 38h			;2f28	ff		.
	rst 38h			;2f29	ff		.
	rst 38h			;2f2a	ff		.
	rst 38h			;2f2b	ff		.
	rst 38h			;2f2c	ff		.
	rst 38h			;2f2d	ff		.
	rst 38h			;2f2e	ff		.
	rst 38h			;2f2f	ff		.
	rst 38h			;2f30	ff		.
	rst 38h			;2f31	ff		.
	rst 38h			;2f32	ff		.
	rst 38h			;2f33	ff		.
	rst 38h			;2f34	ff		.
	rst 38h			;2f35	ff		.
	rst 38h			;2f36	ff		.
	rst 38h			;2f37	ff		.
	rst 38h			;2f38	ff		.
	rst 38h			;2f39	ff		.
	rst 38h			;2f3a	ff		.
	rst 38h			;2f3b	ff		.
	rst 38h			;2f3c	ff		.
	rst 38h			;2f3d	ff		.
	rst 38h			;2f3e	ff		.
	rst 38h			;2f3f	ff		.
	rst 38h			;2f40	ff		.
	rst 38h			;2f41	ff		.
	rst 38h			;2f42	ff		.
	rst 38h			;2f43	ff		.
	rst 38h			;2f44	ff		.
	rst 38h			;2f45	ff		.
	rst 38h			;2f46	ff		.
	rst 38h			;2f47	ff		.
	rst 38h			;2f48	ff		.
	rst 38h			;2f49	ff		.
	rst 38h			;2f4a	ff		.
	rst 38h			;2f4b	ff		.
	rst 38h			;2f4c	ff		.
	rst 38h			;2f4d	ff		.
	rst 38h			;2f4e	ff		.
	rst 38h			;2f4f	ff		.
	rst 38h			;2f50	ff		.
	rst 38h			;2f51	ff		.
	rst 38h			;2f52	ff		.
	rst 38h			;2f53	ff		.
	rst 38h			;2f54	ff		.
	rst 38h			;2f55	ff		.
	rst 38h			;2f56	ff		.
	rst 38h			;2f57	ff		.
	rst 38h			;2f58	ff		.
	rst 38h			;2f59	ff		.
	rst 38h			;2f5a	ff		.
	rst 38h			;2f5b	ff		.
	rst 38h			;2f5c	ff		.
	rst 38h			;2f5d	ff		.
	rst 38h			;2f5e	ff		.
	rst 38h			;2f5f	ff		.
	rst 38h			;2f60	ff		.
	rst 38h			;2f61	ff		.
	rst 38h			;2f62	ff		.
	rst 38h			;2f63	ff		.
	rst 38h			;2f64	ff		.
	rst 38h			;2f65	ff		.
	rst 38h			;2f66	ff		.
	rst 38h			;2f67	ff		.
	rst 38h			;2f68	ff		.
	rst 38h			;2f69	ff		.
	rst 38h			;2f6a	ff		.
	rst 38h			;2f6b	ff		.
	rst 38h			;2f6c	ff		.
	rst 38h			;2f6d	ff		.
	rst 38h			;2f6e	ff		.
	rst 38h			;2f6f	ff		.
	rst 38h			;2f70	ff		.
	rst 38h			;2f71	ff		.
	rst 38h			;2f72	ff		.
	rst 38h			;2f73	ff		.
	rst 38h			;2f74	ff		.
	rst 38h			;2f75	ff		.
	rst 38h			;2f76	ff		.
	rst 38h			;2f77	ff		.
	rst 38h			;2f78	ff		.
	rst 38h			;2f79	ff		.
	rst 38h			;2f7a	ff		.
	rst 38h			;2f7b	ff		.
	rst 38h			;2f7c	ff		.
	rst 38h			;2f7d	ff		.
	rst 38h			;2f7e	ff		.
	rst 38h			;2f7f	ff		.
	rst 38h			;2f80	ff		.
	rst 38h			;2f81	ff		.
	rst 38h			;2f82	ff		.
	rst 38h			;2f83	ff		.
	rst 38h			;2f84	ff		.
	rst 38h			;2f85	ff		.
	rst 38h			;2f86	ff		.
	rst 38h			;2f87	ff		.
	rst 38h			;2f88	ff		.
	rst 38h			;2f89	ff		.
	rst 38h			;2f8a	ff		.
	rst 38h			;2f8b	ff		.
	rst 38h			;2f8c	ff		.
	rst 38h			;2f8d	ff		.
	rst 38h			;2f8e	ff		.
	rst 38h			;2f8f	ff		.
	rst 38h			;2f90	ff		.
	rst 38h			;2f91	ff		.
	rst 38h			;2f92	ff		.
	rst 38h			;2f93	ff		.
	rst 38h			;2f94	ff		.
	rst 38h			;2f95	ff		.
	rst 38h			;2f96	ff		.
	rst 38h			;2f97	ff		.
	rst 38h			;2f98	ff		.
	rst 38h			;2f99	ff		.
	rst 38h			;2f9a	ff		.
	rst 38h			;2f9b	ff		.
	rst 38h			;2f9c	ff		.
	rst 38h			;2f9d	ff		.
	rst 38h			;2f9e	ff		.
	rst 38h			;2f9f	ff		.
	rst 38h			;2fa0	ff		.
	rst 38h			;2fa1	ff		.
	rst 38h			;2fa2	ff		.
	rst 38h			;2fa3	ff		.
	rst 38h			;2fa4	ff		.
	rst 38h			;2fa5	ff		.
	rst 38h			;2fa6	ff		.
	rst 38h			;2fa7	ff		.
	rst 38h			;2fa8	ff		.
	rst 38h			;2fa9	ff		.
	rst 38h			;2faa	ff		.
	rst 38h			;2fab	ff		.
	rst 38h			;2fac	ff		.
	rst 38h			;2fad	ff		.
	rst 38h			;2fae	ff		.
l2fafh:
	rst 38h			;2faf	ff		.
	rst 38h			;2fb0	ff		.
	rst 38h			;2fb1	ff		.
	rst 38h			;2fb2	ff		.
	rst 38h			;2fb3	ff		.
	rst 38h			;2fb4	ff		.
	rst 38h			;2fb5	ff		.
	rst 38h			;2fb6	ff		.
	rst 38h			;2fb7	ff		.
	rst 38h			;2fb8	ff		.
	rst 38h			;2fb9	ff		.
	rst 38h			;2fba	ff		.
	rst 38h			;2fbb	ff		.
	rst 38h			;2fbc	ff		.
	rst 38h			;2fbd	ff		.
	rst 38h			;2fbe	ff		.
	rst 38h			;2fbf	ff		.
	rst 38h			;2fc0	ff		.
	rst 38h			;2fc1	ff		.
	rst 38h			;2fc2	ff		.
	rst 38h			;2fc3	ff		.
	rst 38h			;2fc4	ff		.
	rst 38h			;2fc5	ff		.
	rst 38h			;2fc6	ff		.
	rst 38h			;2fc7	ff		.
	rst 38h			;2fc8	ff		.
	rst 38h			;2fc9	ff		.
	rst 38h			;2fca	ff		.
	rst 38h			;2fcb	ff		.
	rst 38h			;2fcc	ff		.
	rst 38h			;2fcd	ff		.
	rst 38h			;2fce	ff		.
	rst 38h			;2fcf	ff		.
	rst 38h			;2fd0	ff		.
	rst 38h			;2fd1	ff		.
	rst 38h			;2fd2	ff		.
	rst 38h			;2fd3	ff		.
	rst 38h			;2fd4	ff		.
	rst 38h			;2fd5	ff		.
	rst 38h			;2fd6	ff		.
	rst 38h			;2fd7	ff		.
	rst 38h			;2fd8	ff		.
	rst 38h			;2fd9	ff		.
	rst 38h			;2fda	ff		.
	rst 38h			;2fdb	ff		.
	rst 38h			;2fdc	ff		.
	rst 38h			;2fdd	ff		.
	rst 38h			;2fde	ff		.
	rst 38h			;2fdf	ff		.
	rst 38h			;2fe0	ff		.
	rst 38h			;2fe1	ff		.
	rst 38h			;2fe2	ff		.
	rst 38h			;2fe3	ff		.
	rst 38h			;2fe4	ff		.
	rst 38h			;2fe5	ff		.
	rst 38h			;2fe6	ff		.
	rst 38h			;2fe7	ff		.
	rst 38h			;2fe8	ff		.
	rst 38h			;2fe9	ff		.
	rst 38h			;2fea	ff		.
	rst 38h			;2feb	ff		.
	rst 38h			;2fec	ff		.
	rst 38h			;2fed	ff		.
	rst 38h			;2fee	ff		.
	rst 38h			;2fef	ff		.
	rst 38h			;2ff0	ff		.
	rst 38h			;2ff1	ff		.
	rst 38h			;2ff2	ff		.
	rst 38h			;2ff3	ff		.
	rst 38h			;2ff4	ff		.
	rst 38h			;2ff5	ff		.
	rst 38h			;2ff6	ff		.
	rst 38h			;2ff7	ff		.
	rst 38h			;2ff8	ff		.
	rst 38h			;2ff9	ff		.
	rst 38h			;2ffa	ff		.
	rst 38h			;2ffb	ff		.
	rst 38h			;2ffc	ff		.
	rst 38h			;2ffd	ff		.
	rst 38h			;2ffe	ff		.
	rst 38h			;2fff	ff		.
FDD_BASE:
FDD_DISPATCH:
	jp G_MAIN		;3000	c3 45 30	. E 0
F_HOOK_VEC:
	jp F_HOOK		;3003	c3 08 32	. . 2
LOWER_VEC:
	jp LOWER_LOOP		;3006	c3 4f 33	. O 3
CH_OUT_VEC:
	jp G_OUT		;3009	c3 4a 30	. J 0
CH_IN_VEC:
	jp G_IN			;300c	c3 4f 30	. O 0
CH_OPEN_VEC:
	jp G_OPEN		;300f	c3 54 30	. T 0
CH_CLOSE_VEC:
	jp G_CLOSE		;3012	c3 5e 30	. ^ 0
BEEP_VEC:
	jp G_BEEP		;3015	c3 29 30	. ) 0
OPEN_SYN_VEC:
	jp G_OSYN		;3018	c3 59 30	. Y 0
C_END_VEC:
	jp C_END2		;301b	c3 38 33	. 8 3
TAPE_VEC:
	jp TAPE_MODE		;301e	c3 21 30	. ! 0
TAPE_MODE:
	ld a,(05ddbh)		;3021	3a db 5d	: . ]
	res 1,a			;3024	cb 8f		. .
	jp MODE_SET_OK		;3026	c3 05 21	. . !
G_BEEP:
	ld a,h			;3029	7c		|
	and a			;302a	a7		.
	jr nz,G_BEEP.beep	;302b	20 13		  .
	ld a,l			;302d	7d		}
	cp 0c8h			;302e	fe c8		. .
	jr nz,G_BEEP.beep	;3030	20 0e		  .
	push hl			;3032	e5		.
	ld hl,(05c51h)		;3033	2a 51 5c	* Q \
	inc hl			;3036	23		#
	inc hl			;3037	23		#
	inc hl			;3038	23		#
	inc hl			;3039	23		#
	ld a,(hl)		;303a	7e		~
	pop hl			;303b	e1		.
	cp 046h			;303c	fe 46		. F
	jr z,G_BEEP.quiet	;303e	28 03		( .
G_BEEP.beep:
	call ENTRY_TABLE	;3040	cd 00 20	. .  
G_BEEP.quiet:
	di			;3043	f3		.
	ret			;3044	c9		.
G_MAIN:
	ld hl,FDD_MAIN		;3045	21 87 30	! . 0
	jr GUARDED		;3048	18 17		. .
G_OUT:
	ld hl,CH_OUT		;304a	21 62 35	! b 5
	jr GUARDED		;304d	18 12		. .
G_IN:
	ld hl,CH_IN		;304f	21 a1 35	! . 5
	jr GUARDED		;3052	18 0d		. .
G_OPEN:
	ld hl,CH_OPEN_HOOK	;3054	21 5c 33	! \ 3
	jr GUARDED		;3057	18 08		. .
G_OSYN:
	ld hl,OPEN_SYNTAX	;3059	21 8e 34	! . 4
	jr GUARDED		;305c	18 03		. .
G_CLOSE:
	ld hl,CH_CLOSE_HOOK	;305e	21 b3 34	! . 4
GUARDED:
	push hl			;3061	e5		.
	ld hl,(05c3dh)		;3062	2a 3d 5c	* = \
	ex (sp),hl		;3065	e3		.
	push hl			;3066	e5		.
	ld hl,(065ceh)		;3067	2a ce 65	* . e
	inc hl			;306a	23		#
	inc hl			;306b	23		#
	inc hl			;306c	23		#
	inc hl			;306d	23		#
	ex (sp),hl		;306e	e3		.
	push hl			;306f	e5		.
	ld hl,H_TRAP		;3070	21 b2 14	! . .
	ex (sp),hl		;3073	e3		.
	ld (05c3dh),sp		;3074	ed 73 3d 5c	. s = \
	call JP_HL		;3078	cd 86 30	. . 0
	di			;307b	f3		.
	inc sp			;307c	33		3
	inc sp			;307d	33		3
	inc sp			;307e	33		3
	inc sp			;307f	33		3
	ex (sp),hl		;3080	e3		.
	ld (05c3dh),hl		;3081	22 3d 5c	" = \
	pop hl			;3084	e1		.
	ret			;3085	c9		.
JP_HL:
	jp (hl)			;3086	e9		.
FDD_MAIN:
	ld iy,05c3ah		;3087	fd 21 3a 5c	. ! : \
	ei			;308b	fb		.
	ld a,b			;308c	78		x
	cp 0cfh			;308d	fe cf		. .
	jp z,FDD_CAT		;308f	ca b0 30	. . 0
	cp 0d1h			;3092	fe d1		. .
	jp z,FDD_MOVE		;3094	ca ea 30	. . 0
	ld hl,CMD_ERASE		;3097	21 35 37	! 5 7
	cp 0d2h			;309a	fe d2		. .
	jp z,FDD_ONE_ARG	;309c	ca d4 30	. . 0
	ld hl,CMD_FORMAT	;309f	21 40 37	! @ 7
	cp 0d0h			;30a2	fe d0		. .
	jp z,FDD_ONE_ARG	;30a4	ca d4 30	. . 0
	ret			;30a7	c9		.
	ld b,(hl)		;30a8	46		F
	ld b,h			;30a9	44		D
	ld b,h			;30aa	44		D
	ld b,e			;30ab	43		C
	ld c,l			;30ac	4d		M
	ld b,h			;30ad	44		D
	nop			;30ae	00		.
FDD_VERSION:
	ex af,af'		;30af	08		.
FDD_CAT:
	call AT_END		;30b0	cd 60 31	. ` 1
	jr z,FDD_CAT.bare	;30b3	28 15		( .
	call EXPT_STR_END	;30b5	cd 69 31	. i 1
	ret z			;30b8	c8		.
	call POP_STR		;30b9	cd 80 31	. . 1
	ld a,b			;30bc	78		x
	or c			;30bd	b1		.
	ld hl,CMD_TAPDIR	;30be	21 0f 37	! . 7
	jp z,SEND_PREFIX	;30c1	ca b9 31	. . 1
	ld hl,CMD_DIR_ARG	;30c4	21 06 37	! . 7
	jp SEND_ONE		;30c7	c3 bf 31	. . 1
FDD_CAT.bare:
	call RUNTIME		;30ca	cd 71 31	. q 1
	ret z			;30cd	c8		.
	ld hl,CMD_DIR		;30ce	21 fe 36	! . 6
	jp SEND_PREFIX		;30d1	c3 b9 31	. . 1
FDD_ONE_ARG:
	push hl			;30d4	e5		.
	call AT_END		;30d5	cd 60 31	. ` 1
	jr z,NONSENSE		;30d8	28 6b		( k
	call EXPT_STR_END	;30da	cd 69 31	. i 1
	pop hl			;30dd	e1		.
	ret z			;30de	c8		.
	push hl			;30df	e5		.
	call POP_STR		;30e0	cd 80 31	. . 1
	pop hl			;30e3	e1		.
	call NOT_EMPTY		;30e4	cd 99 31	. . 1
	jp SEND_ONE		;30e7	c3 bf 31	. . 1
FDD_MOVE:
	call SKIP_SPACES	;30ea	cd 49 31	. I 1
	cp 0cch			;30ed	fe cc		. .
	jr z,FDD_MOVE.cd	;30ef	28 3c		( <
	call AT_END		;30f1	cd 60 31	. ` 1
	jr z,NONSENSE		;30f4	28 4f		( O
	call HC_EXPT_STR	;30f6	cd 77 31	. w 1
l30f9h:
	call SKIP_SPACES	;30f9	cd 49 31	. I 1
	cp 0cch			;30fc	fe cc		. .
	jr nz,NONSENSE		;30fe	20 45		  E
	call NEXT_CHAR		;3100	cd 58 31	. X 1
	call EXPT_STR_END	;3103	cd 69 31	. i 1
	ret z			;3106	c8		.
	call POP_STR		;3107	cd 80 31	. . 1
	call NOT_EMPTY		;310a	cd 99 31	. . 1
	push de			;310d	d5		.
	push bc			;310e	c5		.
	call POP_STR		;310f	cd 80 31	. . 1
	call NOT_EMPTY		;3112	cd 99 31	. . 1
	push de			;3115	d5		.
	push bc			;3116	c5		.
	ld hl,CMD_COPY		;3117	21 2b 37	! + 7
	call BUILD_START	;311a	cd 9e 31	. . 1
	pop bc			;311d	c1		.
	ex (sp),hl		;311e	e3		.
	ldir			;311f	ed b0		. .
	ld a,07ch		;3121	3e 7c		> |
	ld (de),a		;3123	12		.
	inc de			;3124	13		.
	pop hl			;3125	e1		.
	pop bc			;3126	c1		.
	ex (sp),hl		;3127	e3		.
	ldir			;3128	ed b0		. .
	jp SEND_TAIL		;312a	c3 c8 31	. . 1
FDD_MOVE.cd:
	call NEXT_CHAR		;312d	cd 58 31	. X 1
	call EXPT_STR_END	;3130	cd 69 31	. i 1
	ret z			;3133	c8		.
	call POP_STR		;3134	cd 80 31	. . 1
	ld a,b			;3137	78		x
	or c			;3138	b1		.
	ld hl,CMD_CD_BACK	;3139	21 22 37	! " 7
	jp z,SEND_PREFIX	;313c	ca b9 31	. . 1
	ld hl,CMD_CD		;313f	21 1a 37	! . 7
	jp SEND_ONE		;3142	c3 bf 31	. . 1
NONSENSE:
	rst 8			;3145	cf		.
	dec bc			;3146	0b		.
TOO_LONG:
	rst 8			;3147	cf		.
	ld c,02ah		;3148	0e 2a		. *
	ld e,l			;314a	5d		]
	ld e,h			;314b	5c		\
SKIP_SPACES.loop:
	ld a,(hl)		;314c	7e		~
	cp 020h			;314d	fe 20		.  
	jr nz,SKIP_SPACES.done	;314f	20 03		  .
	inc hl			;3151	23		#
	jr SKIP_SPACES.loop	;3152	18 f8		. .
SKIP_SPACES.done:
	ld (05c5dh),hl		;3154	22 5d 5c	" ] \
	ret			;3157	c9		.
NEXT_CHAR:
	ld hl,(05c5dh)		;3158	2a 5d 5c	* ] \
	inc hl			;315b	23		#
	ld (05c5dh),hl		;315c	22 5d 5c	" ] \
	ret			;315f	c9		.
AT_END:
	call SKIP_SPACES	;3160	cd 49 31	. I 1
	cp 00dh			;3163	fe 0d		. .
	ret z			;3165	c8		.
	cp 03ah			;3166	fe 3a		. :
	ret			;3168	c9		.
EXPT_STR_END:
	call HC_EXPT_STR	;3169	cd 77 31	. w 1
	call AT_END		;316c	cd 60 31	. ` 1
	jr nz,NONSENSE		;316f	20 d4		  .
RUNTIME:
	ld a,(05c3bh)		;3171	3a 3b 5c	: ; \
	and 080h		;3174	e6 80		. .
	ret			;3176	c9		.
HC_EXPT_STR:
	push ix			;3177	dd e5		. .
	exx			;3179	d9		.
	ld hl,H_EXPT_STR	;317a	21 ef 1b	! . .
	jp CALL_HOME		;317d	c3 dd 03	. . .
POP_STR:
	ld hl,(05c65h)		;3180	2a 65 5c	* e \
	dec hl			;3183	2b		+
	ld b,(hl)		;3184	46		F
	dec hl			;3185	2b		+
	ld c,(hl)		;3186	4e		N
	dec hl			;3187	2b		+
	ld d,(hl)		;3188	56		V
	dec hl			;3189	2b		+
	ld e,(hl)		;318a	5e		^
	dec hl			;318b	2b		+
	ld (05c65h),hl		;318c	22 65 5c	" e \
	ld a,b			;318f	78		x
	and a			;3190	a7		.
	jr nz,TOO_LONG		;3191	20 b4		  .
l3193h:
	ld a,c			;3193	79		y
	cp 041h			;3194	fe 41		. A
	jr nc,TOO_LONG		;3196	30 af		0 .
	ret			;3198	c9		.
NOT_EMPTY:
	ld a,b			;3199	78		x
	or c			;319a	b1		.
	ret nz			;319b	c0		.
	jr TOO_LONG		;319c	18 a9		. .
BUILD_START:
	push hl			;319e	e5		.
	ld bc,l00a0h		;319f	01 a0 00	. . .
	call HC_TEST_ROOM	;31a2	cd b0 31	. . 1
	pop hl			;31a5	e1		.
	ld de,(05c65h)		;31a6	ed 5b 65 5c	. [ e \
	push de			;31aa	d5		.
	call COPY_CSTR		;31ab	cd 00 32	. . 2
	pop hl			;31ae	e1		.
	ret			;31af	c9		.
HC_TEST_ROOM:
	push ix			;31b0	dd e5		. .
	exx			;31b2	d9		.
	ld hl,H_TEST_ROOM	;31b3	21 bb 1f	! . .
	jp CALL_HOME		;31b6	c3 dd 03	. . .
SEND_PREFIX:
	call BUILD_START	;31b9	cd 9e 31	. . 1
	push hl			;31bc	e5		.
	jr SEND_TAIL		;31bd	18 09		. .
SEND_ONE:
	push de			;31bf	d5		.
	push bc			;31c0	c5		.
	call BUILD_START	;31c1	cd 9e 31	. . 1
	pop bc			;31c4	c1		.
	ex (sp),hl		;31c5	e3		.
	ldir			;31c6	ed b0		. .
SEND_TAIL:
	pop hl			;31c8	e1		.
	ld a,e			;31c9	7b		{
	sub l			;31ca	95		.
	ld c,a			;31cb	4f		O
	ld a,d			;31cc	7a		z
	sbc a,h			;31cd	9c		.
	ld b,a			;31ce	47		G
	ex de,hl		;31cf	eb		.
	ld (hl),000h		;31d0	36 00		6 .
	inc hl			;31d2	23		#
	ld (hl),e		;31d3	73		s
	inc hl			;31d4	23		#
	ld (hl),d		;31d5	72		r
	inc hl			;31d6	23		#
	ld (hl),c		;31d7	71		q
	inc hl			;31d8	23		#
	ld (hl),b		;31d9	70		p
	inc hl			;31da	23		#
	ld (05c65h),hl		;31db	22 65 5c	" e \
	xor a			;31de	af		.
	ld (05c74h),a		;31df	32 74 5c	2 t \
	ld (05c75h),a		;31e2	32 75 5c	2 u \
TPI_SEND:
	push hl			;31e5	e5		.
	push de			;31e6	d5		.
	ld hl,(05c78h)		;31e7	2a 78 5c	* x \
TPI_SEND.nz:
	inc hl			;31ea	23		#
	ld a,h			;31eb	7c		|
	or l			;31ec	b5		.
	jr z,TPI_SEND.nz	;31ed	28 fb		( .
	ld (05dd1h),hl		;31ef	22 d1 5d	" . ]
	ld hl,(05c65h)		;31f2	2a 65 5c	* e \
	dec hl			;31f5	2b		+
	ld b,(hl)		;31f6	46		F
	dec hl			;31f7	2b		+
	ld c,(hl)		;31f8	4e		N
	dec hl			;31f9	2b		+
	ld d,(hl)		;31fa	56		V
	dec hl			;31fb	2b		+
	ld e,(hl)		;31fc	5e		^
	jp SESSION_NAMED	;31fd	c3 ac 1a	. . .
COPY_CSTR:
	ld a,(hl)		;3200	7e		~
	inc hl			;3201	23		#
	and a			;3202	a7		.
	ret z			;3203	c8		.
	ld (de),a		;3204	12		.
	inc de			;3205	13		.
	jr COPY_CSTR		;3206	18 f8		. .
F_HOOK:
	push hl			;3208	e5		.
	push de			;3209	d5		.
	call PEEK_NAME		;320a	cd 74 32	. t 2
	ld a,b			;320d	78		x
	and a			;320e	a7		.
	jr nz,F_HOOK.stock	;320f	20 5e		  ^
	ld a,c			;3211	79		y
	cp 003h			;3212	fe 03		. .
	jr c,F_HOOK.stock	;3214	38 59		8 Y
	ld a,(de)		;3216	1a		.
	and 0dfh		;3217	e6 df		. .
	cp 046h			;3219	fe 46		. F
	jr nz,F_HOOK.stock	;321b	20 52		  R
	inc de			;321d	13		.
	ld a,(de)		;321e	1a		.
	cp 03ah			;321f	fe 3a		. :
	jr nz,F_HOOK.stock	;3221	20 4c		  L
	ld a,c			;3223	79		y
	cp 043h			;3224	fe 43		. C
	jp nc,TOO_LONG		;3226	d2 47 31	. G 1
	ld hl,(05c78h)		;3229	2a 78 5c	* x \
F_HOOK.nz:
	inc hl			;322c	23		#
	ld a,h			;322d	7c		|
	or l			;322e	b5		.
	jr z,F_HOOK.nz		;322f	28 fb		( .
	ld (05dd1h),hl		;3231	22 d1 5d	" . ]
	push ix			;3234	dd e5		. .
	call SEND_FOPEN		;3236	cd 80 32	. . 2
	pop ix			;3239	dd e1		. .
	ld hl,(05c65h)		;323b	2a 65 5c	* e \
	dec hl			;323e	2b		+
	dec hl			;323f	2b		+
	ld a,(05c74h)		;3240	3a 74 5c	: t \
	and a			;3243	a7		.
	jr nz,F_HOOK.anyname	;3244	20 17		  .
	ld a,(hl)		;3246	7e		~
	sub 002h		;3247	d6 02		. .
	cp 00bh			;3249	fe 0b		. .
	jr c,F_HOOK.fits	;324b	38 02		8 .
	ld a,00ah		;324d	3e 0a		> .
F_HOOK.fits:
	ld (hl),a		;324f	77		w
	dec hl			;3250	2b		+
	dec hl			;3251	2b		+
	ld a,(hl)		;3252	7e		~
	add a,002h		;3253	c6 02		. .
	ld (hl),a		;3255	77		w
	inc hl			;3256	23		#
	ld a,(hl)		;3257	7e		~
	adc a,000h		;3258	ce 00		. .
	ld (hl),a		;325a	77		w
	jr F_HOOK.go		;325b	18 02		. .
F_HOOK.anyname:
	ld (hl),000h		;325d	36 00		6 .
F_HOOK.go:
	ld a,(05ddbh)		;325f	3a db 5d	: . ]
	and 00fh		;3262	e6 0f		. .
	ld (05ddbh),a		;3264	32 db 5d	2 . ]
	pop de			;3267	d1		.
	pop hl			;3268	e1		.
	ld bc,l0010h+1		;3269	01 11 00	. . .
	jp SAVE_ETC_BODY	;326c	c3 d5 01	. . .
F_HOOK.stock:
	pop de			;326f	d1		.
	pop hl			;3270	e1		.
	jp SESSION_SETUP	;3271	c3 73 1a	. s .
PEEK_NAME:
	ld hl,(05c65h)		;3274	2a 65 5c	* e \
	dec hl			;3277	2b		+
	ld b,(hl)		;3278	46		F
	dec hl			;3279	2b		+
	ld c,(hl)		;327a	4e		N
	dec hl			;327b	2b		+
	ld d,(hl)		;327c	56		V
	dec hl			;327d	2b		+
	ld e,(hl)		;327e	5e		^
	ret			;327f	c9		.
SEND_FOPEN:
	ld hl,(05c5dh)		;3280	2a 5d 5c	* ] \
SEND_FOPEN.sp:
	ld a,(hl)		;3283	7e		~
	inc hl			;3284	23		#
	cp 020h			;3285	fe 20		.  
	jr z,SEND_FOPEN.sp	;3287	28 fa		( .
	cp 0afh			;3289	fe af		. .
	jr z,SEND_FOPEN.tok	;328b	28 0d		( .
	cp 0aah			;328d	fe aa		. .
	jr z,SEND_FOPEN.tok	;328f	28 09		( .
	cp 0e4h			;3291	fe e4		. .
	jr z,SEND_FOPEN.tok	;3293	28 05		( .
	cp 0cah			;3295	fe ca		. .
	jr z,SEND_FOPEN.tok	;3297	28 01		( .
	xor a			;3299	af		.
SEND_FOPEN.tok:
	push af			;329a	f5		.
	call PEEK_NAME		;329b	cd 74 32	. t 2
	inc de			;329e	13		.
	inc de			;329f	13		.
	ex de,hl		;32a0	eb		.
	ld a,c			;32a1	79		y
	sub 002h		;32a2	d6 02		. .
	ld b,a			;32a4	47		G
	add a,00ah		;32a5	c6 0a		. .
	ld c,a			;32a7	4f		O
	pop af			;32a8	f1		.
	ld e,a			;32a9	5f		_
	push hl			;32aa	e5		.
	push bc			;32ab	c5		.
	ld a,042h		;32ac	3e 42		> B
	ld d,a			;32ae	57		W
	call SYNC_WRITE		;32af	cd 00 23	. . #
	xor a			;32b2	af		.
	call TXX		;32b3	cd 10 33	. . 3
	ld a,(05dcfh)		;32b6	3a cf 5d	: . ]
	call TXX		;32b9	cd 10 33	. . 3
	ld a,(05c74h)		;32bc	3a 74 5c	: t \
	call TXX		;32bf	cd 10 33	. . 3
	ld a,e			;32c2	7b		{
	call TXX		;32c3	cd 10 33	. . 3
	ld a,(05dd1h)		;32c6	3a d1 5d	: . ]
	call TXX		;32c9	cd 10 33	. . 3
	ld a,(05dd2h)		;32cc	3a d2 5d	: . ]
	call TXX		;32cf	cd 10 33	. . 3
	ld a,c			;32d2	79		y
	call TXX		;32d3	cd 10 33	. . 3
	xor a			;32d6	af		.
	call TXX		;32d7	cd 10 33	. . 3
	ld a,d			;32da	7a		z
	call BIOS_TX_A		;32db	cd 46 18	. F .
	call BIOS_RX_A		;32de	cd 48 18	. H .
	call sub_184ch		;32e1	cd 4c 18	. L .
	jr c,WF_FAIL		;32e4	38 39		8 9
	pop bc			;32e6	c1		.
	pop hl			;32e7	e1		.
	ld a,044h		;32e8	3e 44		> D
	ld d,a			;32ea	57		W
	call BIOS_TX_A		;32eb	cd 46 18	. F .
	ld a,c			;32ee	79		y
	call TXX		;32ef	cd 10 33	. . 3
	xor a			;32f2	af		.
	call TXX		;32f3	cd 10 33	. . 3
	push hl			;32f6	e5		.
	push bc			;32f7	c5		.
	ld hl,FOPEN_TXT		;32f8	21 45 33	! E 3
	ld b,00ah		;32fb	06 0a		. .
	call TX_STR		;32fd	cd 17 33	. . 3
	pop bc			;3300	c1		.
	pop hl			;3301	e1		.
	call TX_STR		;3302	cd 17 33	. . 3
	ld a,d			;3305	7a		z
	call BIOS_TX_A		;3306	cd 46 18	. F .
	call sub_184ah		;3309	cd 4a 18	. J .
	ret nc			;330c	d0		.
	jp C_FAIL		;330d	c3 2d 33	. - 3
TXX:
	push af			;3310	f5		.
	xor d			;3311	aa		.
	ld d,a			;3312	57		W
	pop af			;3313	f1		.
	jp BIOS_TX_A		;3314	c3 46 18	. F .
TX_STR:
	ld a,(hl)		;3317	7e		~
	inc hl			;3318	23		#
	call TXX		;3319	cd 10 33	. . 3
	djnz TX_STR		;331c	10 f9		. .
	ret			;331e	c9		.
WF_FAIL:
	cp 00ch			;331f	fe 0c		. .
	jr z,WF_FAIL.brk	;3321	28 06		( .
	cp 01ch			;3323	fe 1c		. .
	jr z,WF_FAIL.rst	;3325	28 04		( .
	rst 8			;3327	cf		.
	ld (de),a		;3328	12		.
WF_FAIL.brk:
	rst 8			;3329	cf		.
	inc c			;332a	0c		.
WF_FAIL.rst:
	rst 8			;332b	cf		.
	inc e			;332c	1c		.
C_FAIL:
	cp 00ch			;332d	fe 0c		. .
	jr z,WF_FAIL.brk	;332f	28 f8		( .
	cp 01ch			;3331	fe 1c		. .
	jr z,WF_FAIL.rst	;3333	28 f6		( .
	jp STATUS_TO_REPORT	;3335	c3 f3 1b	. . .
C_END2:
	call sub_184ch		;3338	cd 4c 18	. L .
	jp nc,C_END_TAIL	;333b	d2 7f 22	. . "
	cp 002h			;333e	fe 02		. .
	scf			;3340	37		7
	ret nz			;3341	c0		.
	ld a,009h		;3342	3e 09		> .
	ret			;3344	c9		.
FOPEN_TXT:
	ld (hl),h		;3345	74		t
	ld (hl),b		;3346	70		p
	ld l,c			;3347	69		i
	ld a,(06f66h)		;3348	3a 66 6f	: f o
	ld (hl),b		;334b	70		p
	ld h,l			;334c	65		e
	ld l,(hl)		;334d	6e		n
	jr nz,$-49		;334e	20 cd		  .
	cp c			;3350	b9		.
	ld (bc),a		;3351	02		.
	push af			;3352	f5		.
	ld a,0fdh		;3353	3e fd		> .
	call OPEN_STREAM	;3355	cd 26 04	. & .
	pop af			;3358	f1		.
	jp LOOP_BODY		;3359	c3 e6 21	. . !
CH_OPEN_HOOK:
	ld iy,05c3ah		;335c	fd 21 3a 5c	. ! : \
	call PEEK_NAME		;3360	cd 74 32	. t 2
	ld a,b			;3363	78		x
	and a			;3364	a7		.
	jp nz,STRMS_NC		;3365	c2 a4 34	. . 4
	ld a,c			;3368	79		y
	cp 002h			;3369	fe 02		. .
	jp c,STRMS_NC		;336b	da a4 34	. . 4
	inc de			;336e	13		.
	ld a,(de)		;336f	1a		.
	dec de			;3370	1b		.
	cp 03ah			;3371	fe 3a		. :
	jp nz,STRMS_NC		;3373	c2 a4 34	. . 4
	ld a,(de)		;3376	1a		.
	and 0dfh		;3377	e6 df		. .
	cp 044h			;3379	fe 44		. D
	jr z,CH_OPEN_HOOK.ours	;337b	28 0b		( .
	cp 046h			;337d	fe 46		. F
	jp nz,STRMS_NC		;337f	c2 a4 34	. . 4
	ld a,c			;3382	79		y
	cp 003h			;3383	fe 03		. .
	jp c,STRMS_NC		;3385	da a4 34	. . 4
CH_OPEN_HOOK.ours:
	ld a,c			;3388	79		y
	cp 043h			;3389	fe 43		. C
	jp nc,TOO_LONG		;338b	d2 47 31	. G 1
	ld bc,l02a0h		;338e	01 a0 02	. . .
	call HC_TEST_ROOM	;3391	cd b0 31	. . 1
	ld bc,l0000h		;3394	01 00 00	. . .
	call AT_END		;3397	cd 60 31	. ` 1
	jr z,CH_OPEN_HOOK.dflt0	;339a	28 32		( 2
	cp 02ch			;339c	fe 2c		. ,
	jp nz,NONSENSE		;339e	c2 45 31	. E 1
	call NEXT_CHAR		;33a1	cd 58 31	. X 1
	call HC_EXPT_STR	;33a4	cd 77 31	. w 1
	call SKIP_SPACES	;33a7	cd 49 31	. I 1
	ld bc,l0000h		;33aa	01 00 00	. . .
	cp 02ch			;33ad	fe 2c		. ,
	jr nz,CH_OPEN_HOOK.nolen	;33af	20 09		  .
	call NEXT_CHAR		;33b1	cd 58 31	. X 1
	call HC_EXPT_1NUM	;33b4	cd 35 35	. 5 5
	call HC_FIND_INT2	;33b7	cd 3e 35	. > 5
CH_OPEN_HOOK.nolen:
	push bc			;33ba	c5		.
	call AT_END		;33bb	cd 60 31	. ` 1
	jp nz,NONSENSE		;33be	c2 45 31	. E 1
	call POP_STR		;33c1	cd 80 31	. . 1
	ld a,c			;33c4	79		y
	and a			;33c5	a7		.
	jr z,CH_OPEN_HOOK.dflt	;33c6	28 07		( .
	cp 004h			;33c8	fe 04		. .
	jr c,CH_OPEN_HOOK.mode	;33ca	38 09		8 .
	rst 8			;33cc	cf		.
	add hl,de		;33cd	19		.
CH_OPEN_HOOK.dflt0:
	push bc			;33ce	c5		.
CH_OPEN_HOOK.dflt:
	ld de,MODE_R		;33cf	11 77 37	. w 7
	ld bc,l0001h		;33d2	01 01 00	. . .
CH_OPEN_HOOK.mode:
	push bc			;33d5	c5		.
	push de			;33d6	d5		.
	ld hl,CMD_CHOPEN	;33d7	21 6b 37	! k 7
	ld de,(05c65h)		;33da	ed 5b 65 5c	. [ e \
	call COPY_CSTR		;33de	cd 00 32	. . 2
	pop hl			;33e1	e1		.
	pop bc			;33e2	c1		.
	ldir			;33e3	ed b0		. .
	ld a,020h		;33e5	3e 20		>  
	ld (de),a		;33e7	12		.
	inc de			;33e8	13		.
	push de			;33e9	d5		.
	call PEEK_NAME		;33ea	cd 74 32	. t 2
	ld a,(de)		;33ed	1a		.
	and 0dfh		;33ee	e6 df		. .
	cp 044h			;33f0	fe 44		. D
	jr z,CH_OPEN_HOOK.keep	;33f2	28 04		( .
	inc de			;33f4	13		.
	inc de			;33f5	13		.
	dec bc			;33f6	0b		.
	dec bc			;33f7	0b		.
CH_OPEN_HOOK.keep:
	ex de,hl		;33f8	eb		.
	pop de			;33f9	d1		.
	ld a,b			;33fa	78		x
	or c			;33fb	b1		.
	jr z,CH_OPEN_HOOK.none	;33fc	28 02		( .
	ldir			;33fe	ed b0		. .
CH_OPEN_HOOK.none:
	xor a			;3400	af		.
	ld (de),a		;3401	12		.
	pop bc			;3402	c1		.
	push bc			;3403	c5		.
	ld a,b			;3404	78		x
	and a			;3405	a7		.
	jr z,CH_OPEN_HOOK.len	;3406	28 02		( .
	ld c,0ffh		;3408	0e ff		. .
CH_OPEN_HOOK.len:
	ld b,000h		;340a	06 00		. .
	ld hl,(05c65h)		;340c	2a 65 5c	* e \
	ld a,(05ccbh)		;340f	3a cb 5c	: . \
	call CH_SEND		;3412	cd 50 36	. P 6
	call CH_STATUS		;3415	cd 41 36	. A 6
	ld hl,(05c65h)		;3418	2a 65 5c	* e \
	ld de,0fffbh		;341b	11 fb ff	. . .
	add hl,de		;341e	19		.
	ld (05c65h),hl		;341f	22 65 5c	" e \
	ld hl,(05c53h)		;3422	2a 53 5c	* S \
	dec hl			;3425	2b		+
	ld a,(hl)		;3426	7e		~
	cp 080h			;3427	fe 80		. .
	jr z,CH_OPEN_HOOK.end	;3429	28 01		( .
	dec hl			;342b	2b		+
CH_OPEN_HOOK.end:
	push hl			;342c	e5		.
	ld de,(05c4fh)		;342d	ed 5b 4f 5c	. [ O \
	and a			;3431	a7		.
	sbc hl,de		;3432	ed 52		. R
	inc hl			;3434	23		#
	xor a			;3435	af		.
	bit 7,l			;3436	cb 7d		. }
	jr z,CH_OPEN_HOOK.pad	;3438	28 01		( .
	sub l			;343a	95		.
CH_OPEN_HOOK.pad:
	pop hl			;343b	e1		.
	push af			;343c	f5		.
	push hl			;343d	e5		.
	dec hl			;343e	2b		+
	ld bc,CH_ALLOC		;343f	01 00 02	. . .
	call HC_MAKE_ROOM	;3442	cd 47 35	. G 5
	pop hl			;3445	e1		.
	push hl			;3446	e5		.
	ld d,h			;3447	54		T
	ld e,l			;3448	5d		]
	inc de			;3449	13		.
	ld (hl),000h		;344a	36 00		6 .
	ld bc,l01ffh		;344c	01 ff 01	. . .
	ldir			;344f	ed b0		. .
	pop hl			;3451	e1		.
	pop af			;3452	f1		.
	ld e,a			;3453	5f		_
	ld d,000h		;3454	16 00		. .
	add hl,de		;3456	19		.
	push hl			;3457	e5		.
	pop ix			;3458	dd e1		. .
	ld (ix+000h),0a0h	;345a	dd 36 00 a0	. 6 . .
	ld (ix+001h),014h	;345e	dd 36 01 14	. 6 . .
	ld (ix+002h),0a9h	;3462	dd 36 02 a9	. 6 . .
	ld (ix+003h),014h	;3466	dd 36 03 14	. 6 . .
	ld (ix+004h),046h	;346a	dd 36 04 46	. 6 . F
	ld (ix+006h),a		;346e	dd 77 06	. w .
	ld a,(05ccbh)		;3471	3a cb 5c	: . \
	ld (ix+005h),a		;3474	dd 77 05	. w .
	pop bc			;3477	c1		.
	ld a,b			;3478	78		x
	or c			;3479	b1		.
	jr z,CH_OPEN_HOOK.strm	;347a	28 04		( .
	ld (ix+00ah),001h	;347c	dd 36 0a 01	. 6 . .
CH_OPEN_HOOK.strm:
	ld de,(05c4fh)		;3480	ed 5b 4f 5c	. [ O \
	and a			;3484	a7		.
	sbc hl,de		;3485	ed 52		. R
	inc hl			;3487	23		#
	ex de,hl		;3488	eb		.
	call STRMS_HL		;3489	cd a9 34	. . 4
	scf			;348c	37		7
	ret			;348d	c9		.
OPEN_SYNTAX:
	ld iy,05c3ah		;348e	fd 21 3a 5c	. ! : \
	call NEXT_CHAR		;3492	cd 58 31	. X 1
	call HC_EXPT_STR	;3495	cd 77 31	. w 1
	call SKIP_SPACES	;3498	cd 49 31	. I 1
	cp 02ch			;349b	fe 2c		. ,
	ret nz			;349d	c0		.
	call NEXT_CHAR		;349e	cd 58 31	. X 1
	jp HC_EXPT_1NUM		;34a1	c3 35 35	. 5 5
STRMS_NC:
	call STRMS_HL		;34a4	cd a9 34	. . 4
	and a			;34a7	a7		.
	ret			;34a8	c9		.
STRMS_HL:
	ld a,(05ccbh)		;34a9	3a cb 5c	: . \
	add a,a			;34ac	87		.
	add a,016h		;34ad	c6 16		. .
	ld l,a			;34af	6f		o
	ld h,05ch		;34b0	26 5c		& \
	ret			;34b2	c9		.
CH_CLOSE_HOOK:
	ld iy,05c3ah		;34b3	fd 21 3a 5c	. ! : \
	bit 7,b			;34b7	cb 78		. x
	jr nz,CH_CLOSE_HOOK.stock	;34b9	20 0f		  .
	ld hl,(05c4fh)		;34bb	2a 4f 5c	* O \
	add hl,bc		;34be	09		.
	dec hl			;34bf	2b		+
	push hl			;34c0	e5		.
	pop ix			;34c1	dd e1		. .
	ld a,(ix+004h)		;34c3	dd 7e 04	. ~ .
	cp 046h			;34c6	fe 46		. F
	jr z,CH_CLOSE_HOOK.ours	;34c8	28 06		( .
CH_CLOSE_HOOK.stock:
	call STRMS_HL		;34ca	cd a9 34	. . 4
	ld a,b			;34cd	78		x
	or c			;34ce	b1		.
	ret			;34cf	c9		.
CH_CLOSE_HOOK.ours:
	push bc			;34d0	c5		.
	call CH_FLUSH		;34d1	cd d4 35	. . 5
	ld a,(ix+005h)		;34d4	dd 7e 05	. ~ .
	ld hl,CMD_CHCLOSE	;34d7	21 5f 37	! _ 7
	ld bc,l0000h		;34da	01 00 00	. . .
	call CH_SEND		;34dd	cd 50 36	. P 6
	call CH_STATUS		;34e0	cd 41 36	. A 6
	pop bc			;34e3	c1		.
	ld e,(ix+006h)		;34e4	dd 5e 06	. ^ .
	ld d,000h		;34e7	16 00		. .
	push ix			;34e9	dd e5		. .
	pop hl			;34eb	e1		.
	and a			;34ec	a7		.
	sbc hl,de		;34ed	ed 52		. R
	push hl			;34ef	e5		.
	ld hl,05c10h		;34f0	21 10 5c	! . \
	ld a,013h		;34f3	3e 13		> .
CH_CLOSE_HOOK.fix:
	ld e,(hl)		;34f5	5e		^
	inc hl			;34f6	23		#
	ld d,(hl)		;34f7	56		V
	bit 7,d			;34f8	cb 7a		. z
	jr nz,CH_CLOSE_HOOK.next	;34fa	20 0b		  .
	push hl			;34fc	e5		.
	ld h,b			;34fd	60		`
	ld l,c			;34fe	69		i
	and a			;34ff	a7		.
	sbc hl,de		;3500	ed 52		. R
	pop hl			;3502	e1		.
	jr nc,CH_CLOSE_HOOK.next	;3503	30 02		0 .
	dec (hl)		;3505	35		5
	dec (hl)		;3506	35		5
CH_CLOSE_HOOK.next:
	inc hl			;3507	23		#
	dec a			;3508	3d		=
	jr nz,CH_CLOSE_HOOK.fix	;3509	20 ea		  .
	pop hl			;350b	e1		.
	push hl			;350c	e5		.
	ld de,(05c51h)		;350d	ed 5b 51 5c	. [ Q \
	ex de,hl		;3511	eb		.
	and a			;3512	a7		.
	sbc hl,de		;3513	ed 52		. R
	ld a,000h		;3515	3e 00		> .
	jr c,CH_CLOSE_HOOK.keep	;3517	38 08		8 .
	ld a,h			;3519	7c		|
	cp 002h			;351a	fe 02		. .
	ld a,000h		;351c	3e 00		> .
	jr nc,CH_CLOSE_HOOK.keep	;351e	30 01		0 .
	inc a			;3520	3c		<
CH_CLOSE_HOOK.keep:
	pop hl			;3521	e1		.
	push af			;3522	f5		.
	ld bc,CH_ALLOC		;3523	01 00 02	. . .
	call HC_RECLAIM		;3526	cd 50 35	. P 5
	pop af			;3529	f1		.
	and a			;352a	a7		.
	ld a,002h		;352b	3e 02		> .
	call nz,HC_CHAN_OPEN	;352d	c4 59 35	. Y 5
	call STRMS_HL		;3530	cd a9 34	. . 4
	scf			;3533	37		7
	ret			;3534	c9		.
HC_EXPT_1NUM:
	push ix			;3535	dd e5		. .
	exx			;3537	d9		.
	ld hl,H_EXPT_1NUM	;3538	21 e5 1b	! . .
	jp CALL_HOME		;353b	c3 dd 03	. . .
HC_FIND_INT2:
	push ix			;353e	dd e5		. .
	exx			;3540	d9		.
	ld hl,H_FIND_INT2	;3541	21 23 1f	! # .
	jp CALL_HOME		;3544	c3 dd 03	. . .
HC_MAKE_ROOM:
	push ix			;3547	dd e5		. .
	exx			;3549	d9		.
	ld hl,H_MAKE_ROOM	;354a	21 bb 12	! . .
	jp CALL_HOME		;354d	c3 dd 03	. . .
HC_RECLAIM:
	push ix			;3550	dd e5		. .
	exx			;3552	d9		.
	ld hl,H_RECLAIM		;3553	21 50 17	! P .
	jp CALL_HOME		;3556	c3 dd 03	. . .
HC_CHAN_OPEN:
	push ix			;3559	dd e5		. .
	exx			;355b	d9		.
	ld hl,H_CHAN_OPEN	;355c	21 30 12	! 0 .
	jp CALL_HOME		;355f	c3 dd 03	. . .
CH_OUT:
	ld iy,05c3ah		;3562	fd 21 3a 5c	. ! : \
	push ix			;3566	dd e5		. .
	ld ix,(05c51h)		;3568	dd 2a 51 5c	. * Q \
	ld c,a			;356c	4f		O
	cp 017h			;356d	fe 17		. .
	jr nz,CH_OUT.put	;356f	20 08		  .
	ld (ix+008h),000h	;3571	dd 36 08 00	. 6 . .
	ld (ix+009h),000h	;3575	dd 36 09 00	. 6 . .
CH_OUT.put:
	ld a,(ix+007h)		;3579	dd 7e 07	. ~ .
	push ix			;357c	dd e5		. .
	pop hl			;357e	e1		.
	ld de,l000bh		;357f	11 0b 00	. . .
	add hl,de		;3582	19		.
	ld e,a			;3583	5f		_
	ld d,000h		;3584	16 00		. .
	add hl,de		;3586	19		.
	ld (hl),c		;3587	71		q
	inc a			;3588	3c		<
	ld (ix+007h),a		;3589	dd 77 07	. w .
	cp 040h			;358c	fe 40		. @
	jr nc,CH_OUT.send	;358e	30 0b		0 .
	ld a,c			;3590	79		y
	cp 00dh			;3591	fe 0d		. .
	jr nz,CH_OUT.done	;3593	20 09		  .
	bit 0,(ix+00ah)		;3595	dd cb 0a 46	. . . F
	jr z,CH_OUT.done	;3599	28 03		( .
CH_OUT.send:
	call CH_FLUSH		;359b	cd d4 35	. . 5
CH_OUT.done:
	pop ix			;359e	dd e1		. .
	ret			;35a0	c9		.
CH_IN:
	ld iy,05c3ah		;35a1	fd 21 3a 5c	. ! : \
	push ix			;35a5	dd e5		. .
	ld ix,(05c51h)		;35a7	dd 2a 51 5c	. * Q \
CH_IN.again:
	ld a,(ix+009h)		;35ab	dd 7e 09	. ~ .
	cp (ix+008h)		;35ae	dd be 08	. . .
	jr c,CH_IN.have		;35b1	38 0d		8 .
	call CH_FLUSH		;35b3	cd d4 35	. . 5
	call CH_FETCH		;35b6	cd ec 35	. . 5
	jr z,CH_IN.again	;35b9	28 f0		( .
	pop ix			;35bb	dd e1		. .
	xor a			;35bd	af		.
	inc a			;35be	3c		<
	ret			;35bf	c9		.
CH_IN.have:
	ld e,a			;35c0	5f		_
	inc a			;35c1	3c		<
	ld (ix+009h),a		;35c2	dd 77 09	. w .
	ld d,000h		;35c5	16 00		. .
	push ix			;35c7	dd e5		. .
	pop hl			;35c9	e1		.
	add hl,de		;35ca	19		.
	ld de,l004bh		;35cb	11 4b 00	. K .
	add hl,de		;35ce	19		.
	ld a,(hl)		;35cf	7e		~
	pop ix			;35d0	dd e1		. .
	scf			;35d2	37		7
	ret			;35d3	c9		.
CH_FLUSH:
	ld a,(ix+007h)		;35d4	dd 7e 07	. ~ .
	and a			;35d7	a7		.
	ret z			;35d8	c8		.
	ld b,a			;35d9	47		G
	ld (ix+007h),000h	;35da	dd 36 07 00	. 6 . .
	ld c,000h		;35de	0e 00		. .
	ld a,(ix+005h)		;35e0	dd 7e 05	. ~ .
	ld hl,CMD_CHWR		;35e3	21 4c 37	! L 7
	call CH_SEND		;35e6	cd 50 36	. P 6
	jp CH_STATUS		;35e9	c3 41 36	. A 6
CH_FETCH:
	ld b,000h		;35ec	06 00		. .
	ld c,0ffh		;35ee	0e ff		. .
	ld a,(ix+005h)		;35f0	dd 7e 05	. ~ .
	ld hl,CMD_CHRD		;35f3	21 56 37	! V 7
	call CH_SEND		;35f6	cd 50 36	. P 6
	call sub_184ch		;35f9	cd 4c 18	. L .
	jp c,WF_FAIL		;35fc	da 1f 33	. . 3
	call BIOS_RX_A		;35ff	cd 48 18	. H .
	cp 001h			;3602	fe 01		. .
	jr z,CH_FETCH.data	;3604	28 0a		( .
	cp 007h			;3606	fe 07		. .
	jr nz,CH_FETCH.err	;3608	20 02		  .
	or a			;360a	b7		.
	ret			;360b	c9		.
CH_FETCH.err:
	dec a			;360c	3d		=
	jp STATUS_TO_REPORT	;360d	c3 f3 1b	. . .
CH_FETCH.data:
	call BIOS_RX_A		;3610	cd 48 18	. H .
	ld b,a			;3613	47		G
	ld (ix+008h),a		;3614	dd 77 08	. w .
	ld (ix+009h),000h	;3617	dd 36 09 00	. 6 . .
	push ix			;361b	dd e5		. .
	pop hl			;361d	e1		.
	ld de,l004bh		;361e	11 4b 00	. K .
	add hl,de		;3621	19		.
	ld d,000h		;3622	16 00		. .
CH_FETCH.byte:
	ld e,010h		;3624	1e 10		. .
CH_FETCH.dly:
	dec e			;3626	1d		.
	jr nz,CH_FETCH.dly	;3627	20 fd		  .
	call BIOS_RX_A		;3629	cd 48 18	. H .
	ld (hl),a		;362c	77		w
	inc hl			;362d	23		#
	xor d			;362e	aa		.
	ld d,a			;362f	57		W
	djnz CH_FETCH.byte	;3630	10 f2		. .
	ld e,010h		;3632	1e 10		. .
CH_FETCH.dly2:
	dec e			;3634	1d		.
	jr nz,CH_FETCH.dly2	;3635	20 fd		  .
	call BIOS_RX_A		;3637	cd 48 18	. H .
	cp d			;363a	ba		.
	jr nz,CH_FETCH.bad	;363b	20 02		  .
	xor a			;363d	af		.
	ret			;363e	c9		.
CH_FETCH.bad:
	rst 8			;363f	cf		.
	ld a,(de)		;3640	1a		.
CH_STATUS:
	ld hl,(05c51h)		;3641	2a 51 5c	* Q \
	push hl			;3644	e5		.
	call sub_184ah		;3645	cd 4a 18	. J .
	pop hl			;3648	e1		.
	ld (05c51h),hl		;3649	22 51 5c	" Q \
	ret nc			;364c	d0		.
	jp C_FAIL		;364d	c3 2d 33	. - 3
CH_SEND:
	push af			;3650	f5		.
	push hl			;3651	e5		.
	push bc			;3652	c5		.
	call STRLEN		;3653	cd f2 36	. . 6
l3656h:
	pop bc			;3656	c1		.
	add a,b			;3657	80		.
	add a,b			;3658	80		.
	ld e,a			;3659	5f		_
	pop hl			;365a	e1		.
	pop af			;365b	f1		.
	push hl			;365c	e5		.
	push bc			;365d	c5		.
	push af			;365e	f5		.
	ld bc,l0000h		;365f	01 00 00	. . .
CH_SEND.idle:
	in a,(00fh)		;3662	db 0f		. .
	and 048h		;3664	e6 48		. H
	cp 048h			;3666	fe 48		. H
	jr z,CH_SEND.sync	;3668	28 05		( .
	dec bc			;366a	0b		.
	ld a,b			;366b	78		x
	or c			;366c	b1		.
	jr nz,CH_SEND.idle	;366d	20 f3		  .
CH_SEND.sync:
	pop af			;366f	f1		.
	pop bc			;3670	c1		.
	push bc			;3671	c5		.
	push af			;3672	f5		.
	ld a,042h		;3673	3e 42		> B
	ld d,a			;3675	57		W
	call SYNC_WRITE		;3676	cd 00 23	. . #
	xor a			;3679	af		.
	call TXX		;367a	cd 10 33	. . 3
	ld a,(05dcfh)		;367d	3a cf 5d	: . ]
	call TXX		;3680	cd 10 33	. . 3
	pop af			;3683	f1		.
	call TXX		;3684	cd 10 33	. . 3
	xor a			;3687	af		.
	call TXX		;3688	cd 10 33	. . 3
	ld a,c			;368b	79		y
	call TXX		;368c	cd 10 33	. . 3
	xor a			;368f	af		.
	call TXX		;3690	cd 10 33	. . 3
	ld a,e			;3693	7b		{
	call TXX		;3694	cd 10 33	. . 3
	xor a			;3697	af		.
	call TXX		;3698	cd 10 33	. . 3
	ld a,d			;369b	7a		z
	call BIOS_TX_A		;369c	cd 46 18	. F .
	call BIOS_RX_A		;369f	cd 48 18	. H .
	call sub_184ch		;36a2	cd 4c 18	. L .
	jp c,WF_FAIL		;36a5	da 1f 33	. . 3
	ld a,044h		;36a8	3e 44		> D
	ld d,a			;36aa	57		W
	call BIOS_TX_A		;36ab	cd 46 18	. F .
	ld a,e			;36ae	7b		{
	call TXX		;36af	cd 10 33	. . 3
	xor a			;36b2	af		.
	call TXX		;36b3	cd 10 33	. . 3
	pop bc			;36b6	c1		.
	pop hl			;36b7	e1		.
	push bc			;36b8	c5		.
CH_SEND.pre:
	ld a,(hl)		;36b9	7e		~
	inc hl			;36ba	23		#
	and a			;36bb	a7		.
	jr z,CH_SEND.hex	;36bc	28 05		( .
	call TXX		;36be	cd 10 33	. . 3
	jr CH_SEND.pre		;36c1	18 f6		. .
CH_SEND.hex:
	pop bc			;36c3	c1		.
	ld a,b			;36c4	78		x
	and a			;36c5	a7		.
	jr z,CH_SEND.end	;36c6	28 19		( .
	push de			;36c8	d5		.
	push ix			;36c9	dd e5		. .
	pop hl			;36cb	e1		.
	ld de,l000bh		;36cc	11 0b 00	. . .
	add hl,de		;36cf	19		.
	pop de			;36d0	d1		.
CH_SEND.hx:
	ld a,(hl)		;36d1	7e		~
	inc hl			;36d2	23		#
	push af			;36d3	f5		.
	rrca			;36d4	0f		.
	rrca			;36d5	0f		.
	rrca			;36d6	0f		.
	rrca			;36d7	0f		.
	call HEXDIG		;36d8	cd e5 36	. . 6
	pop af			;36db	f1		.
	call HEXDIG		;36dc	cd e5 36	. . 6
	djnz CH_SEND.hx		;36df	10 f0		. .
CH_SEND.end:
	ld a,d			;36e1	7a		z
	jp BIOS_TX_A		;36e2	c3 46 18	. F .
HEXDIG:
	and 00fh		;36e5	e6 0f		. .
	add a,030h		;36e7	c6 30		. 0
	cp 03ah			;36e9	fe 3a		. :
	jr c,HEXDIG.d		;36eb	38 02		8 .
	add a,027h		;36ed	c6 27		. '
HEXDIG.d:
	jp TXX			;36ef	c3 10 33	. . 3
STRLEN:
	ld c,000h		;36f2	0e 00		. .
STRLEN.l:
	ld a,(hl)		;36f4	7e		~
	inc hl			;36f5	23		#
	and a			;36f6	a7		.
	jr z,STRLEN.e		;36f7	28 03		( .
	inc c			;36f9	0c		.
	jr STRLEN.l		;36fa	18 f8		. .
STRLEN.e:
	ld a,c			;36fc	79		y
	ret			;36fd	c9		.
CMD_DIR:
	ld (hl),h		;36fe	74		t
	ld (hl),b		;36ff	70		p
	ld l,c			;3700	69		i
	ld a,(06964h)		;3701	3a 64 69	: d i
	ld (hl),d		;3704	72		r
	nop			;3705	00		.
CMD_DIR_ARG:
	ld (hl),h		;3706	74		t
	ld (hl),b		;3707	70		p
	ld l,c			;3708	69		i
	ld a,(06964h)		;3709	3a 64 69	: d i
	ld (hl),d		;370c	72		r
	jr nz,CMD_TAPDIR	;370d	20 00		  .
CMD_TAPDIR:
	ld (hl),h		;370f	74		t
	ld (hl),b		;3710	70		p
	ld l,c			;3711	69		i
	ld a,(06174h)		;3712	3a 74 61	: t a
	ld (hl),b		;3715	70		p
	ld h,h			;3716	64		d
	ld l,c			;3717	69		i
	ld (hl),d		;3718	72		r
	nop			;3719	00		.
CMD_CD:
	ld (hl),h		;371a	74		t
	ld (hl),b		;371b	70		p
	ld l,c			;371c	69		i
	ld a,(06463h)		;371d	3a 63 64	: c d
	jr nz,CMD_CD_BACK	;3720	20 00		  .
CMD_CD_BACK:
	ld (hl),h		;3722	74		t
	ld (hl),b		;3723	70		p
	ld l,c			;3724	69		i
	ld a,(06463h)		;3725	3a 63 64	: c d
	jr nz,l3757h		;3728	20 2d		  -
	nop			;372a	00		.
CMD_COPY:
	ld (hl),h		;372b	74		t
	ld (hl),b		;372c	70		p
	ld l,c			;372d	69		i
	ld a,(06f63h)		;372e	3a 63 6f	: c o
	ld (hl),b		;3731	70		p
	ld a,c			;3732	79		y
	jr nz,CMD_ERASE		;3733	20 00		  .
CMD_ERASE:
	ld (hl),h		;3735	74		t
	ld (hl),b		;3736	70		p
	ld l,c			;3737	69		i
	ld a,(07265h)		;3738	3a 65 72	: e r
	ld h,c			;373b	61		a
	ld (hl),e		;373c	73		s
	ld h,l			;373d	65		e
	jr nz,CMD_FORMAT	;373e	20 00		  .
CMD_FORMAT:
	ld (hl),h		;3740	74		t
	ld (hl),b		;3741	70		p
	ld l,c			;3742	69		i
	ld a,(06f66h)		;3743	3a 66 6f	: f o
	ld (hl),d		;3746	72		r
	ld l,l			;3747	6d		m
	ld h,c			;3748	61		a
	ld (hl),h		;3749	74		t
	jr nz,CMD_CHWR		;374a	20 00		  .
CMD_CHWR:
	ld (hl),h		;374c	74		t
	ld (hl),b		;374d	70		p
	ld l,c			;374e	69		i
	ld a,(06863h)		;374f	3a 63 68	: c h
	ld (hl),a		;3752	77		w
	ld (hl),d		;3753	72		r
	jr nz,CMD_CHRD		;3754	20 00		  .
CMD_CHRD:
	ld (hl),h		;3756	74		t
l3757h:
	ld (hl),b		;3757	70		p
	ld l,c			;3758	69		i
	ld a,(06863h)		;3759	3a 63 68	: c h
	ld (hl),d		;375c	72		r
	ld h,h			;375d	64		d
	nop			;375e	00		.
CMD_CHCLOSE:
	ld (hl),h		;375f	74		t
	ld (hl),b		;3760	70		p
	ld l,c			;3761	69		i
	ld a,(06863h)		;3762	3a 63 68	: c h
	ld h,e			;3765	63		c
	ld l,h			;3766	6c		l
	ld l,a			;3767	6f		o
	ld (hl),e		;3768	73		s
	ld h,l			;3769	65		e
	nop			;376a	00		.
CMD_CHOPEN:
	ld (hl),h		;376b	74		t
	ld (hl),b		;376c	70		p
	ld l,c			;376d	69		i
	ld a,(06863h)		;376e	3a 63 68	: c h
	ld l,a			;3771	6f		o
	ld (hl),b		;3772	70		p
	ld h,l			;3773	65		e
	ld l,(hl)		;3774	6e		n
	jr nz,MODE_R		;3775	20 00		  .
MODE_R:
	ld (hl),d		;3777	72		r
FDD_END:
	rst 38h			;3778	ff		.
	rst 38h			;3779	ff		.
	rst 38h			;377a	ff		.
	rst 38h			;377b	ff		.
	rst 38h			;377c	ff		.
	rst 38h			;377d	ff		.
	rst 38h			;377e	ff		.
	rst 38h			;377f	ff		.
	rst 38h			;3780	ff		.
	rst 38h			;3781	ff		.
	rst 38h			;3782	ff		.
	rst 38h			;3783	ff		.
	rst 38h			;3784	ff		.
	rst 38h			;3785	ff		.
	rst 38h			;3786	ff		.
	rst 38h			;3787	ff		.
	rst 38h			;3788	ff		.
	rst 38h			;3789	ff		.
	rst 38h			;378a	ff		.
	rst 38h			;378b	ff		.
	rst 38h			;378c	ff		.
	rst 38h			;378d	ff		.
	rst 38h			;378e	ff		.
	rst 38h			;378f	ff		.
	rst 38h			;3790	ff		.
	rst 38h			;3791	ff		.
	rst 38h			;3792	ff		.
	rst 38h			;3793	ff		.
	rst 38h			;3794	ff		.
	rst 38h			;3795	ff		.
	rst 38h			;3796	ff		.
	rst 38h			;3797	ff		.
	rst 38h			;3798	ff		.
	rst 38h			;3799	ff		.
	rst 38h			;379a	ff		.
	rst 38h			;379b	ff		.
	rst 38h			;379c	ff		.
	rst 38h			;379d	ff		.
	rst 38h			;379e	ff		.
	rst 38h			;379f	ff		.
	rst 38h			;37a0	ff		.
	rst 38h			;37a1	ff		.
	rst 38h			;37a2	ff		.
	rst 38h			;37a3	ff		.
	rst 38h			;37a4	ff		.
	rst 38h			;37a5	ff		.
	rst 38h			;37a6	ff		.
	rst 38h			;37a7	ff		.
	rst 38h			;37a8	ff		.
	rst 38h			;37a9	ff		.
	rst 38h			;37aa	ff		.
	rst 38h			;37ab	ff		.
	rst 38h			;37ac	ff		.
	rst 38h			;37ad	ff		.
	rst 38h			;37ae	ff		.
	rst 38h			;37af	ff		.
	rst 38h			;37b0	ff		.
	rst 38h			;37b1	ff		.
	rst 38h			;37b2	ff		.
	rst 38h			;37b3	ff		.
	rst 38h			;37b4	ff		.
	rst 38h			;37b5	ff		.
	rst 38h			;37b6	ff		.
	rst 38h			;37b7	ff		.
	rst 38h			;37b8	ff		.
	rst 38h			;37b9	ff		.
	rst 38h			;37ba	ff		.
	rst 38h			;37bb	ff		.
	rst 38h			;37bc	ff		.
	rst 38h			;37bd	ff		.
	rst 38h			;37be	ff		.
	rst 38h			;37bf	ff		.
	rst 38h			;37c0	ff		.
	rst 38h			;37c1	ff		.
	rst 38h			;37c2	ff		.
	rst 38h			;37c3	ff		.
	rst 38h			;37c4	ff		.
	rst 38h			;37c5	ff		.
	rst 38h			;37c6	ff		.
	rst 38h			;37c7	ff		.
	rst 38h			;37c8	ff		.
	rst 38h			;37c9	ff		.
	rst 38h			;37ca	ff		.
	rst 38h			;37cb	ff		.
	rst 38h			;37cc	ff		.
	rst 38h			;37cd	ff		.
	rst 38h			;37ce	ff		.
	rst 38h			;37cf	ff		.
	rst 38h			;37d0	ff		.
	rst 38h			;37d1	ff		.
	rst 38h			;37d2	ff		.
	rst 38h			;37d3	ff		.
	rst 38h			;37d4	ff		.
	rst 38h			;37d5	ff		.
	rst 38h			;37d6	ff		.
	rst 38h			;37d7	ff		.
	rst 38h			;37d8	ff		.
	rst 38h			;37d9	ff		.
	rst 38h			;37da	ff		.
	rst 38h			;37db	ff		.
	rst 38h			;37dc	ff		.
	rst 38h			;37dd	ff		.
	rst 38h			;37de	ff		.
	rst 38h			;37df	ff		.
	rst 38h			;37e0	ff		.
	rst 38h			;37e1	ff		.
	rst 38h			;37e2	ff		.
	rst 38h			;37e3	ff		.
	rst 38h			;37e4	ff		.
	rst 38h			;37e5	ff		.
	rst 38h			;37e6	ff		.
	rst 38h			;37e7	ff		.
	rst 38h			;37e8	ff		.
	rst 38h			;37e9	ff		.
	rst 38h			;37ea	ff		.
	rst 38h			;37eb	ff		.
	rst 38h			;37ec	ff		.
	rst 38h			;37ed	ff		.
	rst 38h			;37ee	ff		.
	rst 38h			;37ef	ff		.
	rst 38h			;37f0	ff		.
	rst 38h			;37f1	ff		.
	rst 38h			;37f2	ff		.
	rst 38h			;37f3	ff		.
	rst 38h			;37f4	ff		.
	rst 38h			;37f5	ff		.
	rst 38h			;37f6	ff		.
	rst 38h			;37f7	ff		.
	rst 38h			;37f8	ff		.
	rst 38h			;37f9	ff		.
	rst 38h			;37fa	ff		.
	rst 38h			;37fb	ff		.
	rst 38h			;37fc	ff		.
	rst 38h			;37fd	ff		.
	rst 38h			;37fe	ff		.
	rst 38h			;37ff	ff		.
	rst 38h			;3800	ff		.
	rst 38h			;3801	ff		.
	rst 38h			;3802	ff		.
	rst 38h			;3803	ff		.
	rst 38h			;3804	ff		.
	rst 38h			;3805	ff		.
	rst 38h			;3806	ff		.
	rst 38h			;3807	ff		.
	rst 38h			;3808	ff		.
	rst 38h			;3809	ff		.
	rst 38h			;380a	ff		.
	rst 38h			;380b	ff		.
	rst 38h			;380c	ff		.
	rst 38h			;380d	ff		.
	rst 38h			;380e	ff		.
	rst 38h			;380f	ff		.
	rst 38h			;3810	ff		.
	rst 38h			;3811	ff		.
	rst 38h			;3812	ff		.
	rst 38h			;3813	ff		.
	rst 38h			;3814	ff		.
	rst 38h			;3815	ff		.
	rst 38h			;3816	ff		.
	rst 38h			;3817	ff		.
	rst 38h			;3818	ff		.
	rst 38h			;3819	ff		.
	rst 38h			;381a	ff		.
	rst 38h			;381b	ff		.
	rst 38h			;381c	ff		.
	rst 38h			;381d	ff		.
	rst 38h			;381e	ff		.
	rst 38h			;381f	ff		.
	rst 38h			;3820	ff		.
	rst 38h			;3821	ff		.
	rst 38h			;3822	ff		.
	rst 38h			;3823	ff		.
	rst 38h			;3824	ff		.
	rst 38h			;3825	ff		.
	rst 38h			;3826	ff		.
	rst 38h			;3827	ff		.
	rst 38h			;3828	ff		.
	rst 38h			;3829	ff		.
	rst 38h			;382a	ff		.
	rst 38h			;382b	ff		.
	rst 38h			;382c	ff		.
	rst 38h			;382d	ff		.
	rst 38h			;382e	ff		.
	rst 38h			;382f	ff		.
	rst 38h			;3830	ff		.
	rst 38h			;3831	ff		.
	rst 38h			;3832	ff		.
	rst 38h			;3833	ff		.
	rst 38h			;3834	ff		.
	rst 38h			;3835	ff		.
	rst 38h			;3836	ff		.
	rst 38h			;3837	ff		.
	rst 38h			;3838	ff		.
	rst 38h			;3839	ff		.
	rst 38h			;383a	ff		.
	rst 38h			;383b	ff		.
	rst 38h			;383c	ff		.
	rst 38h			;383d	ff		.
	rst 38h			;383e	ff		.
	rst 38h			;383f	ff		.
	rst 38h			;3840	ff		.
	rst 38h			;3841	ff		.
	rst 38h			;3842	ff		.
	rst 38h			;3843	ff		.
	rst 38h			;3844	ff		.
	rst 38h			;3845	ff		.
	rst 38h			;3846	ff		.
	rst 38h			;3847	ff		.
	rst 38h			;3848	ff		.
	rst 38h			;3849	ff		.
	rst 38h			;384a	ff		.
	rst 38h			;384b	ff		.
	rst 38h			;384c	ff		.
	rst 38h			;384d	ff		.
	rst 38h			;384e	ff		.
	rst 38h			;384f	ff		.
	rst 38h			;3850	ff		.
	rst 38h			;3851	ff		.
	rst 38h			;3852	ff		.
	rst 38h			;3853	ff		.
	rst 38h			;3854	ff		.
	rst 38h			;3855	ff		.
	rst 38h			;3856	ff		.
	rst 38h			;3857	ff		.
	rst 38h			;3858	ff		.
	rst 38h			;3859	ff		.
	rst 38h			;385a	ff		.
	rst 38h			;385b	ff		.
	rst 38h			;385c	ff		.
	rst 38h			;385d	ff		.
	rst 38h			;385e	ff		.
	rst 38h			;385f	ff		.
	rst 38h			;3860	ff		.
	rst 38h			;3861	ff		.
	rst 38h			;3862	ff		.
	rst 38h			;3863	ff		.
	rst 38h			;3864	ff		.
	rst 38h			;3865	ff		.
	rst 38h			;3866	ff		.
	rst 38h			;3867	ff		.
	rst 38h			;3868	ff		.
	rst 38h			;3869	ff		.
	rst 38h			;386a	ff		.
	rst 38h			;386b	ff		.
	rst 38h			;386c	ff		.
	rst 38h			;386d	ff		.
	rst 38h			;386e	ff		.
	rst 38h			;386f	ff		.
	rst 38h			;3870	ff		.
	rst 38h			;3871	ff		.
	rst 38h			;3872	ff		.
	rst 38h			;3873	ff		.
	rst 38h			;3874	ff		.
	rst 38h			;3875	ff		.
	rst 38h			;3876	ff		.
	rst 38h			;3877	ff		.
	rst 38h			;3878	ff		.
	rst 38h			;3879	ff		.
	rst 38h			;387a	ff		.
	rst 38h			;387b	ff		.
	rst 38h			;387c	ff		.
	rst 38h			;387d	ff		.
	rst 38h			;387e	ff		.
	rst 38h			;387f	ff		.
	rst 38h			;3880	ff		.
	rst 38h			;3881	ff		.
	rst 38h			;3882	ff		.
	rst 38h			;3883	ff		.
	rst 38h			;3884	ff		.
	rst 38h			;3885	ff		.
	rst 38h			;3886	ff		.
	rst 38h			;3887	ff		.
	rst 38h			;3888	ff		.
	rst 38h			;3889	ff		.
	rst 38h			;388a	ff		.
	rst 38h			;388b	ff		.
	rst 38h			;388c	ff		.
	rst 38h			;388d	ff		.
	rst 38h			;388e	ff		.
	rst 38h			;388f	ff		.
	rst 38h			;3890	ff		.
	rst 38h			;3891	ff		.
	rst 38h			;3892	ff		.
	rst 38h			;3893	ff		.
	rst 38h			;3894	ff		.
	rst 38h			;3895	ff		.
	rst 38h			;3896	ff		.
	rst 38h			;3897	ff		.
	rst 38h			;3898	ff		.
	rst 38h			;3899	ff		.
	rst 38h			;389a	ff		.
	rst 38h			;389b	ff		.
	rst 38h			;389c	ff		.
	rst 38h			;389d	ff		.
	rst 38h			;389e	ff		.
	rst 38h			;389f	ff		.
	rst 38h			;38a0	ff		.
	rst 38h			;38a1	ff		.
	rst 38h			;38a2	ff		.
	rst 38h			;38a3	ff		.
	rst 38h			;38a4	ff		.
	rst 38h			;38a5	ff		.
	rst 38h			;38a6	ff		.
	rst 38h			;38a7	ff		.
	rst 38h			;38a8	ff		.
	rst 38h			;38a9	ff		.
	rst 38h			;38aa	ff		.
	rst 38h			;38ab	ff		.
	rst 38h			;38ac	ff		.
	rst 38h			;38ad	ff		.
	rst 38h			;38ae	ff		.
	rst 38h			;38af	ff		.
	rst 38h			;38b0	ff		.
	rst 38h			;38b1	ff		.
	rst 38h			;38b2	ff		.
	rst 38h			;38b3	ff		.
	rst 38h			;38b4	ff		.
	rst 38h			;38b5	ff		.
	rst 38h			;38b6	ff		.
	rst 38h			;38b7	ff		.
	rst 38h			;38b8	ff		.
	rst 38h			;38b9	ff		.
	rst 38h			;38ba	ff		.
	rst 38h			;38bb	ff		.
	rst 38h			;38bc	ff		.
	rst 38h			;38bd	ff		.
	rst 38h			;38be	ff		.
	rst 38h			;38bf	ff		.
	rst 38h			;38c0	ff		.
	rst 38h			;38c1	ff		.
	rst 38h			;38c2	ff		.
	rst 38h			;38c3	ff		.
	rst 38h			;38c4	ff		.
	rst 38h			;38c5	ff		.
	rst 38h			;38c6	ff		.
	rst 38h			;38c7	ff		.
	rst 38h			;38c8	ff		.
	rst 38h			;38c9	ff		.
	rst 38h			;38ca	ff		.
	rst 38h			;38cb	ff		.
	rst 38h			;38cc	ff		.
	rst 38h			;38cd	ff		.
	rst 38h			;38ce	ff		.
	rst 38h			;38cf	ff		.
	rst 38h			;38d0	ff		.
	rst 38h			;38d1	ff		.
	rst 38h			;38d2	ff		.
	rst 38h			;38d3	ff		.
	rst 38h			;38d4	ff		.
	rst 38h			;38d5	ff		.
	rst 38h			;38d6	ff		.
	rst 38h			;38d7	ff		.
	rst 38h			;38d8	ff		.
	rst 38h			;38d9	ff		.
	rst 38h			;38da	ff		.
	rst 38h			;38db	ff		.
	rst 38h			;38dc	ff		.
	rst 38h			;38dd	ff		.
	rst 38h			;38de	ff		.
	rst 38h			;38df	ff		.
	rst 38h			;38e0	ff		.
	rst 38h			;38e1	ff		.
	rst 38h			;38e2	ff		.
	rst 38h			;38e3	ff		.
	rst 38h			;38e4	ff		.
	rst 38h			;38e5	ff		.
	rst 38h			;38e6	ff		.
	rst 38h			;38e7	ff		.
	rst 38h			;38e8	ff		.
	rst 38h			;38e9	ff		.
	rst 38h			;38ea	ff		.
	rst 38h			;38eb	ff		.
	rst 38h			;38ec	ff		.
	rst 38h			;38ed	ff		.
	rst 38h			;38ee	ff		.
	rst 38h			;38ef	ff		.
	rst 38h			;38f0	ff		.
	rst 38h			;38f1	ff		.
	rst 38h			;38f2	ff		.
	rst 38h			;38f3	ff		.
	rst 38h			;38f4	ff		.
	rst 38h			;38f5	ff		.
	rst 38h			;38f6	ff		.
	rst 38h			;38f7	ff		.
	rst 38h			;38f8	ff		.
	rst 38h			;38f9	ff		.
	rst 38h			;38fa	ff		.
	rst 38h			;38fb	ff		.
	rst 38h			;38fc	ff		.
	rst 38h			;38fd	ff		.
	rst 38h			;38fe	ff		.
	rst 38h			;38ff	ff		.
	rst 38h			;3900	ff		.
	rst 38h			;3901	ff		.
	rst 38h			;3902	ff		.
	rst 38h			;3903	ff		.
	rst 38h			;3904	ff		.
	rst 38h			;3905	ff		.
	rst 38h			;3906	ff		.
	rst 38h			;3907	ff		.
	rst 38h			;3908	ff		.
	rst 38h			;3909	ff		.
	rst 38h			;390a	ff		.
	rst 38h			;390b	ff		.
	rst 38h			;390c	ff		.
	rst 38h			;390d	ff		.
	rst 38h			;390e	ff		.
	rst 38h			;390f	ff		.
	rst 38h			;3910	ff		.
	rst 38h			;3911	ff		.
	rst 38h			;3912	ff		.
	rst 38h			;3913	ff		.
	rst 38h			;3914	ff		.
	rst 38h			;3915	ff		.
	rst 38h			;3916	ff		.
	rst 38h			;3917	ff		.
	rst 38h			;3918	ff		.
	rst 38h			;3919	ff		.
	rst 38h			;391a	ff		.
	rst 38h			;391b	ff		.
	rst 38h			;391c	ff		.
	rst 38h			;391d	ff		.
	rst 38h			;391e	ff		.
	rst 38h			;391f	ff		.
	rst 38h			;3920	ff		.
	rst 38h			;3921	ff		.
	rst 38h			;3922	ff		.
	rst 38h			;3923	ff		.
	rst 38h			;3924	ff		.
	rst 38h			;3925	ff		.
	rst 38h			;3926	ff		.
	rst 38h			;3927	ff		.
	rst 38h			;3928	ff		.
	rst 38h			;3929	ff		.
	rst 38h			;392a	ff		.
	rst 38h			;392b	ff		.
	rst 38h			;392c	ff		.
	rst 38h			;392d	ff		.
	rst 38h			;392e	ff		.
	rst 38h			;392f	ff		.
	rst 38h			;3930	ff		.
	rst 38h			;3931	ff		.
	rst 38h			;3932	ff		.
	rst 38h			;3933	ff		.
	rst 38h			;3934	ff		.
	rst 38h			;3935	ff		.
	rst 38h			;3936	ff		.
	rst 38h			;3937	ff		.
	rst 38h			;3938	ff		.
	rst 38h			;3939	ff		.
	rst 38h			;393a	ff		.
	rst 38h			;393b	ff		.
	rst 38h			;393c	ff		.
	rst 38h			;393d	ff		.
	rst 38h			;393e	ff		.
	rst 38h			;393f	ff		.
	rst 38h			;3940	ff		.
	rst 38h			;3941	ff		.
	rst 38h			;3942	ff		.
	rst 38h			;3943	ff		.
	rst 38h			;3944	ff		.
	rst 38h			;3945	ff		.
	rst 38h			;3946	ff		.
	rst 38h			;3947	ff		.
	rst 38h			;3948	ff		.
	rst 38h			;3949	ff		.
	rst 38h			;394a	ff		.
	rst 38h			;394b	ff		.
	rst 38h			;394c	ff		.
	rst 38h			;394d	ff		.
	rst 38h			;394e	ff		.
	rst 38h			;394f	ff		.
	rst 38h			;3950	ff		.
	rst 38h			;3951	ff		.
	rst 38h			;3952	ff		.
	rst 38h			;3953	ff		.
	rst 38h			;3954	ff		.
	rst 38h			;3955	ff		.
	rst 38h			;3956	ff		.
	rst 38h			;3957	ff		.
	rst 38h			;3958	ff		.
	rst 38h			;3959	ff		.
	rst 38h			;395a	ff		.
	rst 38h			;395b	ff		.
	rst 38h			;395c	ff		.
	rst 38h			;395d	ff		.
	rst 38h			;395e	ff		.
	rst 38h			;395f	ff		.
	rst 38h			;3960	ff		.
	rst 38h			;3961	ff		.
	rst 38h			;3962	ff		.
	rst 38h			;3963	ff		.
	rst 38h			;3964	ff		.
	rst 38h			;3965	ff		.
	rst 38h			;3966	ff		.
	rst 38h			;3967	ff		.
	rst 38h			;3968	ff		.
	rst 38h			;3969	ff		.
	rst 38h			;396a	ff		.
	rst 38h			;396b	ff		.
	rst 38h			;396c	ff		.
	rst 38h			;396d	ff		.
	rst 38h			;396e	ff		.
	rst 38h			;396f	ff		.
	rst 38h			;3970	ff		.
	rst 38h			;3971	ff		.
	rst 38h			;3972	ff		.
	rst 38h			;3973	ff		.
	rst 38h			;3974	ff		.
	rst 38h			;3975	ff		.
	rst 38h			;3976	ff		.
	rst 38h			;3977	ff		.
	rst 38h			;3978	ff		.
	rst 38h			;3979	ff		.
	rst 38h			;397a	ff		.
	rst 38h			;397b	ff		.
	rst 38h			;397c	ff		.
	rst 38h			;397d	ff		.
	rst 38h			;397e	ff		.
	rst 38h			;397f	ff		.
	rst 38h			;3980	ff		.
	rst 38h			;3981	ff		.
	rst 38h			;3982	ff		.
	rst 38h			;3983	ff		.
	rst 38h			;3984	ff		.
	rst 38h			;3985	ff		.
	rst 38h			;3986	ff		.
	rst 38h			;3987	ff		.
	rst 38h			;3988	ff		.
	rst 38h			;3989	ff		.
	rst 38h			;398a	ff		.
	rst 38h			;398b	ff		.
	rst 38h			;398c	ff		.
	rst 38h			;398d	ff		.
	rst 38h			;398e	ff		.
	rst 38h			;398f	ff		.
	rst 38h			;3990	ff		.
	rst 38h			;3991	ff		.
	rst 38h			;3992	ff		.
	rst 38h			;3993	ff		.
	rst 38h			;3994	ff		.
	rst 38h			;3995	ff		.
	rst 38h			;3996	ff		.
	rst 38h			;3997	ff		.
	rst 38h			;3998	ff		.
	rst 38h			;3999	ff		.
	rst 38h			;399a	ff		.
	rst 38h			;399b	ff		.
	rst 38h			;399c	ff		.
	rst 38h			;399d	ff		.
	rst 38h			;399e	ff		.
	rst 38h			;399f	ff		.
	rst 38h			;39a0	ff		.
	rst 38h			;39a1	ff		.
	rst 38h			;39a2	ff		.
	rst 38h			;39a3	ff		.
	rst 38h			;39a4	ff		.
	rst 38h			;39a5	ff		.
	rst 38h			;39a6	ff		.
	rst 38h			;39a7	ff		.
	rst 38h			;39a8	ff		.
	rst 38h			;39a9	ff		.
	rst 38h			;39aa	ff		.
	rst 38h			;39ab	ff		.
	rst 38h			;39ac	ff		.
	rst 38h			;39ad	ff		.
	rst 38h			;39ae	ff		.
	rst 38h			;39af	ff		.
	rst 38h			;39b0	ff		.
	rst 38h			;39b1	ff		.
	rst 38h			;39b2	ff		.
	rst 38h			;39b3	ff		.
	rst 38h			;39b4	ff		.
	rst 38h			;39b5	ff		.
	rst 38h			;39b6	ff		.
	rst 38h			;39b7	ff		.
	rst 38h			;39b8	ff		.
	rst 38h			;39b9	ff		.
	rst 38h			;39ba	ff		.
	rst 38h			;39bb	ff		.
	rst 38h			;39bc	ff		.
	rst 38h			;39bd	ff		.
	rst 38h			;39be	ff		.
	rst 38h			;39bf	ff		.
	rst 38h			;39c0	ff		.
	rst 38h			;39c1	ff		.
	rst 38h			;39c2	ff		.
	rst 38h			;39c3	ff		.
	rst 38h			;39c4	ff		.
	rst 38h			;39c5	ff		.
	rst 38h			;39c6	ff		.
	rst 38h			;39c7	ff		.
	rst 38h			;39c8	ff		.
	rst 38h			;39c9	ff		.
	rst 38h			;39ca	ff		.
	rst 38h			;39cb	ff		.
	rst 38h			;39cc	ff		.
	rst 38h			;39cd	ff		.
	rst 38h			;39ce	ff		.
	rst 38h			;39cf	ff		.
	rst 38h			;39d0	ff		.
	rst 38h			;39d1	ff		.
	rst 38h			;39d2	ff		.
	rst 38h			;39d3	ff		.
	rst 38h			;39d4	ff		.
	rst 38h			;39d5	ff		.
	rst 38h			;39d6	ff		.
	rst 38h			;39d7	ff		.
	rst 38h			;39d8	ff		.
	rst 38h			;39d9	ff		.
	rst 38h			;39da	ff		.
	rst 38h			;39db	ff		.
	rst 38h			;39dc	ff		.
	rst 38h			;39dd	ff		.
	rst 38h			;39de	ff		.
	rst 38h			;39df	ff		.
	rst 38h			;39e0	ff		.
	rst 38h			;39e1	ff		.
	rst 38h			;39e2	ff		.
	rst 38h			;39e3	ff		.
	rst 38h			;39e4	ff		.
	rst 38h			;39e5	ff		.
	rst 38h			;39e6	ff		.
	rst 38h			;39e7	ff		.
	rst 38h			;39e8	ff		.
	rst 38h			;39e9	ff		.
	rst 38h			;39ea	ff		.
	rst 38h			;39eb	ff		.
	rst 38h			;39ec	ff		.
	rst 38h			;39ed	ff		.
	rst 38h			;39ee	ff		.
	rst 38h			;39ef	ff		.
	rst 38h			;39f0	ff		.
	rst 38h			;39f1	ff		.
	rst 38h			;39f2	ff		.
	rst 38h			;39f3	ff		.
	rst 38h			;39f4	ff		.
	rst 38h			;39f5	ff		.
	rst 38h			;39f6	ff		.
	rst 38h			;39f7	ff		.
	rst 38h			;39f8	ff		.
	rst 38h			;39f9	ff		.
	rst 38h			;39fa	ff		.
	rst 38h			;39fb	ff		.
	rst 38h			;39fc	ff		.
	rst 38h			;39fd	ff		.
	rst 38h			;39fe	ff		.
	rst 38h			;39ff	ff		.
	rst 38h			;3a00	ff		.
	rst 38h			;3a01	ff		.
	rst 38h			;3a02	ff		.
	rst 38h			;3a03	ff		.
	rst 38h			;3a04	ff		.
	rst 38h			;3a05	ff		.
	rst 38h			;3a06	ff		.
	rst 38h			;3a07	ff		.
	rst 38h			;3a08	ff		.
	rst 38h			;3a09	ff		.
	rst 38h			;3a0a	ff		.
	rst 38h			;3a0b	ff		.
	rst 38h			;3a0c	ff		.
	rst 38h			;3a0d	ff		.
	rst 38h			;3a0e	ff		.
	rst 38h			;3a0f	ff		.
	rst 38h			;3a10	ff		.
	rst 38h			;3a11	ff		.
	rst 38h			;3a12	ff		.
	rst 38h			;3a13	ff		.
	rst 38h			;3a14	ff		.
	rst 38h			;3a15	ff		.
	rst 38h			;3a16	ff		.
	rst 38h			;3a17	ff		.
	rst 38h			;3a18	ff		.
	rst 38h			;3a19	ff		.
	rst 38h			;3a1a	ff		.
	rst 38h			;3a1b	ff		.
	rst 38h			;3a1c	ff		.
	rst 38h			;3a1d	ff		.
	rst 38h			;3a1e	ff		.
	rst 38h			;3a1f	ff		.
	rst 38h			;3a20	ff		.
	rst 38h			;3a21	ff		.
	rst 38h			;3a22	ff		.
	rst 38h			;3a23	ff		.
	rst 38h			;3a24	ff		.
	rst 38h			;3a25	ff		.
	rst 38h			;3a26	ff		.
	rst 38h			;3a27	ff		.
	rst 38h			;3a28	ff		.
	rst 38h			;3a29	ff		.
	rst 38h			;3a2a	ff		.
	rst 38h			;3a2b	ff		.
	rst 38h			;3a2c	ff		.
	rst 38h			;3a2d	ff		.
	rst 38h			;3a2e	ff		.
	rst 38h			;3a2f	ff		.
	rst 38h			;3a30	ff		.
	rst 38h			;3a31	ff		.
	rst 38h			;3a32	ff		.
	rst 38h			;3a33	ff		.
	rst 38h			;3a34	ff		.
	rst 38h			;3a35	ff		.
	rst 38h			;3a36	ff		.
	rst 38h			;3a37	ff		.
	rst 38h			;3a38	ff		.
	rst 38h			;3a39	ff		.
	rst 38h			;3a3a	ff		.
	rst 38h			;3a3b	ff		.
	rst 38h			;3a3c	ff		.
	rst 38h			;3a3d	ff		.
	rst 38h			;3a3e	ff		.
	rst 38h			;3a3f	ff		.
	rst 38h			;3a40	ff		.
	rst 38h			;3a41	ff		.
	rst 38h			;3a42	ff		.
	rst 38h			;3a43	ff		.
	rst 38h			;3a44	ff		.
	rst 38h			;3a45	ff		.
	rst 38h			;3a46	ff		.
	rst 38h			;3a47	ff		.
	rst 38h			;3a48	ff		.
	rst 38h			;3a49	ff		.
	rst 38h			;3a4a	ff		.
	rst 38h			;3a4b	ff		.
	rst 38h			;3a4c	ff		.
	rst 38h			;3a4d	ff		.
	rst 38h			;3a4e	ff		.
	rst 38h			;3a4f	ff		.
	rst 38h			;3a50	ff		.
	rst 38h			;3a51	ff		.
	rst 38h			;3a52	ff		.
	rst 38h			;3a53	ff		.
	rst 38h			;3a54	ff		.
	rst 38h			;3a55	ff		.
	rst 38h			;3a56	ff		.
	rst 38h			;3a57	ff		.
	rst 38h			;3a58	ff		.
	rst 38h			;3a59	ff		.
	rst 38h			;3a5a	ff		.
	rst 38h			;3a5b	ff		.
	rst 38h			;3a5c	ff		.
	rst 38h			;3a5d	ff		.
	rst 38h			;3a5e	ff		.
	rst 38h			;3a5f	ff		.
	rst 38h			;3a60	ff		.
	rst 38h			;3a61	ff		.
	rst 38h			;3a62	ff		.
	rst 38h			;3a63	ff		.
	rst 38h			;3a64	ff		.
l3a65h:
	rst 38h			;3a65	ff		.
	rst 38h			;3a66	ff		.
	rst 38h			;3a67	ff		.
	rst 38h			;3a68	ff		.
	rst 38h			;3a69	ff		.
	rst 38h			;3a6a	ff		.
	rst 38h			;3a6b	ff		.
	rst 38h			;3a6c	ff		.
	rst 38h			;3a6d	ff		.
	rst 38h			;3a6e	ff		.
	rst 38h			;3a6f	ff		.
	rst 38h			;3a70	ff		.
	rst 38h			;3a71	ff		.
	rst 38h			;3a72	ff		.
	rst 38h			;3a73	ff		.
	rst 38h			;3a74	ff		.
	rst 38h			;3a75	ff		.
	rst 38h			;3a76	ff		.
	rst 38h			;3a77	ff		.
	rst 38h			;3a78	ff		.
	rst 38h			;3a79	ff		.
	rst 38h			;3a7a	ff		.
	rst 38h			;3a7b	ff		.
	rst 38h			;3a7c	ff		.
	rst 38h			;3a7d	ff		.
	rst 38h			;3a7e	ff		.
	rst 38h			;3a7f	ff		.
	rst 38h			;3a80	ff		.
	rst 38h			;3a81	ff		.
	rst 38h			;3a82	ff		.
	rst 38h			;3a83	ff		.
	rst 38h			;3a84	ff		.
	rst 38h			;3a85	ff		.
	rst 38h			;3a86	ff		.
	rst 38h			;3a87	ff		.
	rst 38h			;3a88	ff		.
	rst 38h			;3a89	ff		.
	rst 38h			;3a8a	ff		.
	rst 38h			;3a8b	ff		.
	rst 38h			;3a8c	ff		.
	rst 38h			;3a8d	ff		.
	rst 38h			;3a8e	ff		.
	rst 38h			;3a8f	ff		.
	rst 38h			;3a90	ff		.
	rst 38h			;3a91	ff		.
	rst 38h			;3a92	ff		.
	rst 38h			;3a93	ff		.
	rst 38h			;3a94	ff		.
	rst 38h			;3a95	ff		.
	rst 38h			;3a96	ff		.
	rst 38h			;3a97	ff		.
	rst 38h			;3a98	ff		.
	rst 38h			;3a99	ff		.
	rst 38h			;3a9a	ff		.
	rst 38h			;3a9b	ff		.
	rst 38h			;3a9c	ff		.
	rst 38h			;3a9d	ff		.
	rst 38h			;3a9e	ff		.
	rst 38h			;3a9f	ff		.
	rst 38h			;3aa0	ff		.
	rst 38h			;3aa1	ff		.
	rst 38h			;3aa2	ff		.
	rst 38h			;3aa3	ff		.
	rst 38h			;3aa4	ff		.
	rst 38h			;3aa5	ff		.
	rst 38h			;3aa6	ff		.
	rst 38h			;3aa7	ff		.
	rst 38h			;3aa8	ff		.
	rst 38h			;3aa9	ff		.
	rst 38h			;3aaa	ff		.
	rst 38h			;3aab	ff		.
	rst 38h			;3aac	ff		.
	rst 38h			;3aad	ff		.
	rst 38h			;3aae	ff		.
	rst 38h			;3aaf	ff		.
	rst 38h			;3ab0	ff		.
	rst 38h			;3ab1	ff		.
	rst 38h			;3ab2	ff		.
	rst 38h			;3ab3	ff		.
	rst 38h			;3ab4	ff		.
	rst 38h			;3ab5	ff		.
	rst 38h			;3ab6	ff		.
	rst 38h			;3ab7	ff		.
	rst 38h			;3ab8	ff		.
	rst 38h			;3ab9	ff		.
	rst 38h			;3aba	ff		.
	rst 38h			;3abb	ff		.
	rst 38h			;3abc	ff		.
	rst 38h			;3abd	ff		.
	rst 38h			;3abe	ff		.
	rst 38h			;3abf	ff		.
	rst 38h			;3ac0	ff		.
	rst 38h			;3ac1	ff		.
	rst 38h			;3ac2	ff		.
	rst 38h			;3ac3	ff		.
	rst 38h			;3ac4	ff		.
	rst 38h			;3ac5	ff		.
	rst 38h			;3ac6	ff		.
	rst 38h			;3ac7	ff		.
	rst 38h			;3ac8	ff		.
	rst 38h			;3ac9	ff		.
l3acah:
	rst 38h			;3aca	ff		.
	rst 38h			;3acb	ff		.
	rst 38h			;3acc	ff		.
	rst 38h			;3acd	ff		.
	rst 38h			;3ace	ff		.
	rst 38h			;3acf	ff		.
	rst 38h			;3ad0	ff		.
	rst 38h			;3ad1	ff		.
	rst 38h			;3ad2	ff		.
	rst 38h			;3ad3	ff		.
	rst 38h			;3ad4	ff		.
	rst 38h			;3ad5	ff		.
	rst 38h			;3ad6	ff		.
	rst 38h			;3ad7	ff		.
	rst 38h			;3ad8	ff		.
	rst 38h			;3ad9	ff		.
	rst 38h			;3ada	ff		.
	rst 38h			;3adb	ff		.
	rst 38h			;3adc	ff		.
	rst 38h			;3add	ff		.
	rst 38h			;3ade	ff		.
	rst 38h			;3adf	ff		.
	rst 38h			;3ae0	ff		.
	rst 38h			;3ae1	ff		.
	rst 38h			;3ae2	ff		.
	rst 38h			;3ae3	ff		.
	rst 38h			;3ae4	ff		.
	rst 38h			;3ae5	ff		.
	rst 38h			;3ae6	ff		.
	rst 38h			;3ae7	ff		.
	rst 38h			;3ae8	ff		.
	rst 38h			;3ae9	ff		.
	rst 38h			;3aea	ff		.
	rst 38h			;3aeb	ff		.
	rst 38h			;3aec	ff		.
	rst 38h			;3aed	ff		.
	rst 38h			;3aee	ff		.
	rst 38h			;3aef	ff		.
	rst 38h			;3af0	ff		.
	rst 38h			;3af1	ff		.
	rst 38h			;3af2	ff		.
	rst 38h			;3af3	ff		.
	rst 38h			;3af4	ff		.
	rst 38h			;3af5	ff		.
	rst 38h			;3af6	ff		.
	rst 38h			;3af7	ff		.
	rst 38h			;3af8	ff		.
	rst 38h			;3af9	ff		.
	rst 38h			;3afa	ff		.
	rst 38h			;3afb	ff		.
	rst 38h			;3afc	ff		.
	rst 38h			;3afd	ff		.
	rst 38h			;3afe	ff		.
	rst 38h			;3aff	ff		.
l3b00h:
	rst 38h			;3b00	ff		.
	rst 38h			;3b01	ff		.
	rst 38h			;3b02	ff		.
	rst 38h			;3b03	ff		.
	rst 38h			;3b04	ff		.
	rst 38h			;3b05	ff		.
	rst 38h			;3b06	ff		.
	rst 38h			;3b07	ff		.
	rst 38h			;3b08	ff		.
	rst 38h			;3b09	ff		.
	rst 38h			;3b0a	ff		.
	rst 38h			;3b0b	ff		.
	rst 38h			;3b0c	ff		.
	rst 38h			;3b0d	ff		.
l3b0eh:
	rst 38h			;3b0e	ff		.
	rst 38h			;3b0f	ff		.
	rst 38h			;3b10	ff		.
	rst 38h			;3b11	ff		.
	rst 38h			;3b12	ff		.
	rst 38h			;3b13	ff		.
	rst 38h			;3b14	ff		.
	rst 38h			;3b15	ff		.
	rst 38h			;3b16	ff		.
	rst 38h			;3b17	ff		.
	rst 38h			;3b18	ff		.
	rst 38h			;3b19	ff		.
	rst 38h			;3b1a	ff		.
	rst 38h			;3b1b	ff		.
	rst 38h			;3b1c	ff		.
	rst 38h			;3b1d	ff		.
	rst 38h			;3b1e	ff		.
	rst 38h			;3b1f	ff		.
	rst 38h			;3b20	ff		.
	rst 38h			;3b21	ff		.
	rst 38h			;3b22	ff		.
	rst 38h			;3b23	ff		.
	rst 38h			;3b24	ff		.
	rst 38h			;3b25	ff		.
	rst 38h			;3b26	ff		.
	rst 38h			;3b27	ff		.
	rst 38h			;3b28	ff		.
	rst 38h			;3b29	ff		.
	rst 38h			;3b2a	ff		.
	rst 38h			;3b2b	ff		.
	rst 38h			;3b2c	ff		.
	rst 38h			;3b2d	ff		.
	rst 38h			;3b2e	ff		.
	rst 38h			;3b2f	ff		.
	rst 38h			;3b30	ff		.
	rst 38h			;3b31	ff		.
	rst 38h			;3b32	ff		.
	rst 38h			;3b33	ff		.
	rst 38h			;3b34	ff		.
	rst 38h			;3b35	ff		.
	rst 38h			;3b36	ff		.
	rst 38h			;3b37	ff		.
	rst 38h			;3b38	ff		.
	rst 38h			;3b39	ff		.
	rst 38h			;3b3a	ff		.
	rst 38h			;3b3b	ff		.
	rst 38h			;3b3c	ff		.
	rst 38h			;3b3d	ff		.
	rst 38h			;3b3e	ff		.
	rst 38h			;3b3f	ff		.
	rst 38h			;3b40	ff		.
	rst 38h			;3b41	ff		.
	rst 38h			;3b42	ff		.
	rst 38h			;3b43	ff		.
	rst 38h			;3b44	ff		.
	rst 38h			;3b45	ff		.
	rst 38h			;3b46	ff		.
	rst 38h			;3b47	ff		.
	rst 38h			;3b48	ff		.
	rst 38h			;3b49	ff		.
	rst 38h			;3b4a	ff		.
	rst 38h			;3b4b	ff		.
	rst 38h			;3b4c	ff		.
	rst 38h			;3b4d	ff		.
	rst 38h			;3b4e	ff		.
	rst 38h			;3b4f	ff		.
	rst 38h			;3b50	ff		.
	rst 38h			;3b51	ff		.
	rst 38h			;3b52	ff		.
	rst 38h			;3b53	ff		.
	rst 38h			;3b54	ff		.
	rst 38h			;3b55	ff		.
	rst 38h			;3b56	ff		.
	rst 38h			;3b57	ff		.
	rst 38h			;3b58	ff		.
	rst 38h			;3b59	ff		.
	rst 38h			;3b5a	ff		.
	rst 38h			;3b5b	ff		.
	rst 38h			;3b5c	ff		.
	rst 38h			;3b5d	ff		.
	rst 38h			;3b5e	ff		.
	rst 38h			;3b5f	ff		.
	rst 38h			;3b60	ff		.
	rst 38h			;3b61	ff		.
	rst 38h			;3b62	ff		.
	rst 38h			;3b63	ff		.
	rst 38h			;3b64	ff		.
	rst 38h			;3b65	ff		.
	rst 38h			;3b66	ff		.
	rst 38h			;3b67	ff		.
	rst 38h			;3b68	ff		.
	rst 38h			;3b69	ff		.
	rst 38h			;3b6a	ff		.
	rst 38h			;3b6b	ff		.
	rst 38h			;3b6c	ff		.
	rst 38h			;3b6d	ff		.
	rst 38h			;3b6e	ff		.
	rst 38h			;3b6f	ff		.
	rst 38h			;3b70	ff		.
	rst 38h			;3b71	ff		.
	rst 38h			;3b72	ff		.
	rst 38h			;3b73	ff		.
	rst 38h			;3b74	ff		.
	rst 38h			;3b75	ff		.
	rst 38h			;3b76	ff		.
	rst 38h			;3b77	ff		.
	rst 38h			;3b78	ff		.
	rst 38h			;3b79	ff		.
	rst 38h			;3b7a	ff		.
	rst 38h			;3b7b	ff		.
	rst 38h			;3b7c	ff		.
	rst 38h			;3b7d	ff		.
	rst 38h			;3b7e	ff		.
	rst 38h			;3b7f	ff		.
	rst 38h			;3b80	ff		.
	rst 38h			;3b81	ff		.
	rst 38h			;3b82	ff		.
	rst 38h			;3b83	ff		.
	rst 38h			;3b84	ff		.
	rst 38h			;3b85	ff		.
	rst 38h			;3b86	ff		.
	rst 38h			;3b87	ff		.
	rst 38h			;3b88	ff		.
	rst 38h			;3b89	ff		.
	rst 38h			;3b8a	ff		.
	rst 38h			;3b8b	ff		.
	rst 38h			;3b8c	ff		.
	rst 38h			;3b8d	ff		.
	rst 38h			;3b8e	ff		.
	rst 38h			;3b8f	ff		.
	rst 38h			;3b90	ff		.
	rst 38h			;3b91	ff		.
	rst 38h			;3b92	ff		.
	rst 38h			;3b93	ff		.
	rst 38h			;3b94	ff		.
	rst 38h			;3b95	ff		.
	rst 38h			;3b96	ff		.
	rst 38h			;3b97	ff		.
	rst 38h			;3b98	ff		.
	rst 38h			;3b99	ff		.
	rst 38h			;3b9a	ff		.
	rst 38h			;3b9b	ff		.
	rst 38h			;3b9c	ff		.
	rst 38h			;3b9d	ff		.
	rst 38h			;3b9e	ff		.
	rst 38h			;3b9f	ff		.
	rst 38h			;3ba0	ff		.
	rst 38h			;3ba1	ff		.
	rst 38h			;3ba2	ff		.
	rst 38h			;3ba3	ff		.
	rst 38h			;3ba4	ff		.
	rst 38h			;3ba5	ff		.
	rst 38h			;3ba6	ff		.
	rst 38h			;3ba7	ff		.
	rst 38h			;3ba8	ff		.
	rst 38h			;3ba9	ff		.
	rst 38h			;3baa	ff		.
	rst 38h			;3bab	ff		.
	rst 38h			;3bac	ff		.
	rst 38h			;3bad	ff		.
	rst 38h			;3bae	ff		.
	rst 38h			;3baf	ff		.
	rst 38h			;3bb0	ff		.
	rst 38h			;3bb1	ff		.
	rst 38h			;3bb2	ff		.
	rst 38h			;3bb3	ff		.
	rst 38h			;3bb4	ff		.
	rst 38h			;3bb5	ff		.
	rst 38h			;3bb6	ff		.
	rst 38h			;3bb7	ff		.
	rst 38h			;3bb8	ff		.
	rst 38h			;3bb9	ff		.
	rst 38h			;3bba	ff		.
	rst 38h			;3bbb	ff		.
	rst 38h			;3bbc	ff		.
	rst 38h			;3bbd	ff		.
	rst 38h			;3bbe	ff		.
	rst 38h			;3bbf	ff		.
	rst 38h			;3bc0	ff		.
	rst 38h			;3bc1	ff		.
	rst 38h			;3bc2	ff		.
	rst 38h			;3bc3	ff		.
	rst 38h			;3bc4	ff		.
	rst 38h			;3bc5	ff		.
	rst 38h			;3bc6	ff		.
	rst 38h			;3bc7	ff		.
	rst 38h			;3bc8	ff		.
	rst 38h			;3bc9	ff		.
	rst 38h			;3bca	ff		.
	rst 38h			;3bcb	ff		.
	rst 38h			;3bcc	ff		.
	rst 38h			;3bcd	ff		.
	rst 38h			;3bce	ff		.
	rst 38h			;3bcf	ff		.
	rst 38h			;3bd0	ff		.
	rst 38h			;3bd1	ff		.
	rst 38h			;3bd2	ff		.
	rst 38h			;3bd3	ff		.
	rst 38h			;3bd4	ff		.
	rst 38h			;3bd5	ff		.
	rst 38h			;3bd6	ff		.
	rst 38h			;3bd7	ff		.
	rst 38h			;3bd8	ff		.
	rst 38h			;3bd9	ff		.
	rst 38h			;3bda	ff		.
	rst 38h			;3bdb	ff		.
	rst 38h			;3bdc	ff		.
	rst 38h			;3bdd	ff		.
	rst 38h			;3bde	ff		.
	rst 38h			;3bdf	ff		.
	rst 38h			;3be0	ff		.
	rst 38h			;3be1	ff		.
	rst 38h			;3be2	ff		.
	rst 38h			;3be3	ff		.
	rst 38h			;3be4	ff		.
	rst 38h			;3be5	ff		.
	rst 38h			;3be6	ff		.
	rst 38h			;3be7	ff		.
	rst 38h			;3be8	ff		.
	rst 38h			;3be9	ff		.
	rst 38h			;3bea	ff		.
	rst 38h			;3beb	ff		.
	rst 38h			;3bec	ff		.
	rst 38h			;3bed	ff		.
	rst 38h			;3bee	ff		.
	rst 38h			;3bef	ff		.
	rst 38h			;3bf0	ff		.
	rst 38h			;3bf1	ff		.
	rst 38h			;3bf2	ff		.
	rst 38h			;3bf3	ff		.
	rst 38h			;3bf4	ff		.
	rst 38h			;3bf5	ff		.
	rst 38h			;3bf6	ff		.
	rst 38h			;3bf7	ff		.
	rst 38h			;3bf8	ff		.
	rst 38h			;3bf9	ff		.
	rst 38h			;3bfa	ff		.
	rst 38h			;3bfb	ff		.
	rst 38h			;3bfc	ff		.
	rst 38h			;3bfd	ff		.
	rst 38h			;3bfe	ff		.
	rst 38h			;3bff	ff		.
	rst 38h			;3c00	ff		.
	rst 38h			;3c01	ff		.
	rst 38h			;3c02	ff		.
	rst 38h			;3c03	ff		.
	rst 38h			;3c04	ff		.
	rst 38h			;3c05	ff		.
	rst 38h			;3c06	ff		.
	rst 38h			;3c07	ff		.
	rst 38h			;3c08	ff		.
	rst 38h			;3c09	ff		.
	rst 38h			;3c0a	ff		.
	rst 38h			;3c0b	ff		.
	rst 38h			;3c0c	ff		.
	rst 38h			;3c0d	ff		.
	rst 38h			;3c0e	ff		.
	rst 38h			;3c0f	ff		.
	rst 38h			;3c10	ff		.
	rst 38h			;3c11	ff		.
	rst 38h			;3c12	ff		.
	rst 38h			;3c13	ff		.
	rst 38h			;3c14	ff		.
	rst 38h			;3c15	ff		.
	rst 38h			;3c16	ff		.
	rst 38h			;3c17	ff		.
	rst 38h			;3c18	ff		.
	rst 38h			;3c19	ff		.
	rst 38h			;3c1a	ff		.
	rst 38h			;3c1b	ff		.
	rst 38h			;3c1c	ff		.
	rst 38h			;3c1d	ff		.
	rst 38h			;3c1e	ff		.
	rst 38h			;3c1f	ff		.
	rst 38h			;3c20	ff		.
	rst 38h			;3c21	ff		.
	rst 38h			;3c22	ff		.
	rst 38h			;3c23	ff		.
	rst 38h			;3c24	ff		.
	rst 38h			;3c25	ff		.
	rst 38h			;3c26	ff		.
	rst 38h			;3c27	ff		.
	rst 38h			;3c28	ff		.
	rst 38h			;3c29	ff		.
	rst 38h			;3c2a	ff		.
	rst 38h			;3c2b	ff		.
	rst 38h			;3c2c	ff		.
	rst 38h			;3c2d	ff		.
	rst 38h			;3c2e	ff		.
	rst 38h			;3c2f	ff		.
	rst 38h			;3c30	ff		.
	rst 38h			;3c31	ff		.
	rst 38h			;3c32	ff		.
	rst 38h			;3c33	ff		.
	rst 38h			;3c34	ff		.
	rst 38h			;3c35	ff		.
	rst 38h			;3c36	ff		.
	rst 38h			;3c37	ff		.
	rst 38h			;3c38	ff		.
	rst 38h			;3c39	ff		.
	rst 38h			;3c3a	ff		.
	rst 38h			;3c3b	ff		.
	rst 38h			;3c3c	ff		.
	rst 38h			;3c3d	ff		.
	rst 38h			;3c3e	ff		.
	rst 38h			;3c3f	ff		.
	rst 38h			;3c40	ff		.
	rst 38h			;3c41	ff		.
	rst 38h			;3c42	ff		.
	rst 38h			;3c43	ff		.
	rst 38h			;3c44	ff		.
	rst 38h			;3c45	ff		.
	rst 38h			;3c46	ff		.
	rst 38h			;3c47	ff		.
	rst 38h			;3c48	ff		.
	rst 38h			;3c49	ff		.
	rst 38h			;3c4a	ff		.
	rst 38h			;3c4b	ff		.
	rst 38h			;3c4c	ff		.
	rst 38h			;3c4d	ff		.
	rst 38h			;3c4e	ff		.
	rst 38h			;3c4f	ff		.
	rst 38h			;3c50	ff		.
	rst 38h			;3c51	ff		.
	rst 38h			;3c52	ff		.
	rst 38h			;3c53	ff		.
	rst 38h			;3c54	ff		.
	rst 38h			;3c55	ff		.
	rst 38h			;3c56	ff		.
	rst 38h			;3c57	ff		.
	rst 38h			;3c58	ff		.
	rst 38h			;3c59	ff		.
	rst 38h			;3c5a	ff		.
	rst 38h			;3c5b	ff		.
	rst 38h			;3c5c	ff		.
	rst 38h			;3c5d	ff		.
	rst 38h			;3c5e	ff		.
	rst 38h			;3c5f	ff		.
	rst 38h			;3c60	ff		.
	rst 38h			;3c61	ff		.
	rst 38h			;3c62	ff		.
	rst 38h			;3c63	ff		.
	rst 38h			;3c64	ff		.
	rst 38h			;3c65	ff		.
	rst 38h			;3c66	ff		.
	rst 38h			;3c67	ff		.
	rst 38h			;3c68	ff		.
	rst 38h			;3c69	ff		.
	rst 38h			;3c6a	ff		.
	rst 38h			;3c6b	ff		.
	rst 38h			;3c6c	ff		.
	rst 38h			;3c6d	ff		.
	rst 38h			;3c6e	ff		.
	rst 38h			;3c6f	ff		.
	rst 38h			;3c70	ff		.
	rst 38h			;3c71	ff		.
	rst 38h			;3c72	ff		.
	rst 38h			;3c73	ff		.
	rst 38h			;3c74	ff		.
	rst 38h			;3c75	ff		.
	rst 38h			;3c76	ff		.
	rst 38h			;3c77	ff		.
	rst 38h			;3c78	ff		.
	rst 38h			;3c79	ff		.
	rst 38h			;3c7a	ff		.
	rst 38h			;3c7b	ff		.
	rst 38h			;3c7c	ff		.
	rst 38h			;3c7d	ff		.
	rst 38h			;3c7e	ff		.
	rst 38h			;3c7f	ff		.
	rst 38h			;3c80	ff		.
	rst 38h			;3c81	ff		.
	rst 38h			;3c82	ff		.
	rst 38h			;3c83	ff		.
	rst 38h			;3c84	ff		.
	rst 38h			;3c85	ff		.
	rst 38h			;3c86	ff		.
	rst 38h			;3c87	ff		.
	rst 38h			;3c88	ff		.
l3c89h:
	rst 38h			;3c89	ff		.
	rst 38h			;3c8a	ff		.
	rst 38h			;3c8b	ff		.
	rst 38h			;3c8c	ff		.
	rst 38h			;3c8d	ff		.
	rst 38h			;3c8e	ff		.
	rst 38h			;3c8f	ff		.
	rst 38h			;3c90	ff		.
	rst 38h			;3c91	ff		.
	rst 38h			;3c92	ff		.
	rst 38h			;3c93	ff		.
	rst 38h			;3c94	ff		.
	rst 38h			;3c95	ff		.
	rst 38h			;3c96	ff		.
	rst 38h			;3c97	ff		.
	rst 38h			;3c98	ff		.
	rst 38h			;3c99	ff		.
	rst 38h			;3c9a	ff		.
	rst 38h			;3c9b	ff		.
	rst 38h			;3c9c	ff		.
	rst 38h			;3c9d	ff		.
	rst 38h			;3c9e	ff		.
	rst 38h			;3c9f	ff		.
	rst 38h			;3ca0	ff		.
	rst 38h			;3ca1	ff		.
	rst 38h			;3ca2	ff		.
	rst 38h			;3ca3	ff		.
	rst 38h			;3ca4	ff		.
	rst 38h			;3ca5	ff		.
	rst 38h			;3ca6	ff		.
	rst 38h			;3ca7	ff		.
l3ca8h:
	rst 38h			;3ca8	ff		.
	rst 38h			;3ca9	ff		.
	rst 38h			;3caa	ff		.
	rst 38h			;3cab	ff		.
	rst 38h			;3cac	ff		.
	rst 38h			;3cad	ff		.
	rst 38h			;3cae	ff		.
	rst 38h			;3caf	ff		.
	rst 38h			;3cb0	ff		.
	rst 38h			;3cb1	ff		.
	rst 38h			;3cb2	ff		.
	rst 38h			;3cb3	ff		.
	rst 38h			;3cb4	ff		.
	rst 38h			;3cb5	ff		.
	rst 38h			;3cb6	ff		.
	rst 38h			;3cb7	ff		.
	rst 38h			;3cb8	ff		.
	rst 38h			;3cb9	ff		.
	rst 38h			;3cba	ff		.
	rst 38h			;3cbb	ff		.
	rst 38h			;3cbc	ff		.
	rst 38h			;3cbd	ff		.
	rst 38h			;3cbe	ff		.
	rst 38h			;3cbf	ff		.
	rst 38h			;3cc0	ff		.
	rst 38h			;3cc1	ff		.
	rst 38h			;3cc2	ff		.
	rst 38h			;3cc3	ff		.
	rst 38h			;3cc4	ff		.
	rst 38h			;3cc5	ff		.
	rst 38h			;3cc6	ff		.
	rst 38h			;3cc7	ff		.
	rst 38h			;3cc8	ff		.
	rst 38h			;3cc9	ff		.
	rst 38h			;3cca	ff		.
	rst 38h			;3ccb	ff		.
	rst 38h			;3ccc	ff		.
	rst 38h			;3ccd	ff		.
	rst 38h			;3cce	ff		.
	rst 38h			;3ccf	ff		.
	rst 38h			;3cd0	ff		.
	rst 38h			;3cd1	ff		.
	rst 38h			;3cd2	ff		.
	rst 38h			;3cd3	ff		.
	rst 38h			;3cd4	ff		.
	rst 38h			;3cd5	ff		.
	rst 38h			;3cd6	ff		.
	rst 38h			;3cd7	ff		.
	rst 38h			;3cd8	ff		.
	rst 38h			;3cd9	ff		.
	rst 38h			;3cda	ff		.
	rst 38h			;3cdb	ff		.
l3cdch:
	rst 38h			;3cdc	ff		.
	rst 38h			;3cdd	ff		.
	rst 38h			;3cde	ff		.
	rst 38h			;3cdf	ff		.
	rst 38h			;3ce0	ff		.
	rst 38h			;3ce1	ff		.
	rst 38h			;3ce2	ff		.
	rst 38h			;3ce3	ff		.
	rst 38h			;3ce4	ff		.
	rst 38h			;3ce5	ff		.
	rst 38h			;3ce6	ff		.
	rst 38h			;3ce7	ff		.
	rst 38h			;3ce8	ff		.
	rst 38h			;3ce9	ff		.
	rst 38h			;3cea	ff		.
	rst 38h			;3ceb	ff		.
	rst 38h			;3cec	ff		.
	rst 38h			;3ced	ff		.
	rst 38h			;3cee	ff		.
	rst 38h			;3cef	ff		.
	rst 38h			;3cf0	ff		.
	rst 38h			;3cf1	ff		.
	rst 38h			;3cf2	ff		.
	rst 38h			;3cf3	ff		.
	rst 38h			;3cf4	ff		.
	rst 38h			;3cf5	ff		.
	rst 38h			;3cf6	ff		.
	rst 38h			;3cf7	ff		.
	rst 38h			;3cf8	ff		.
	rst 38h			;3cf9	ff		.
	rst 38h			;3cfa	ff		.
	rst 38h			;3cfb	ff		.
	rst 38h			;3cfc	ff		.
	rst 38h			;3cfd	ff		.
	rst 38h			;3cfe	ff		.
	rst 38h			;3cff	ff		.
	rst 38h			;3d00	ff		.
	rst 38h			;3d01	ff		.
	rst 38h			;3d02	ff		.
	rst 38h			;3d03	ff		.
	rst 38h			;3d04	ff		.
	rst 38h			;3d05	ff		.
	rst 38h			;3d06	ff		.
	rst 38h			;3d07	ff		.
	rst 38h			;3d08	ff		.
	rst 38h			;3d09	ff		.
	rst 38h			;3d0a	ff		.
	rst 38h			;3d0b	ff		.
	rst 38h			;3d0c	ff		.
	rst 38h			;3d0d	ff		.
	rst 38h			;3d0e	ff		.
	rst 38h			;3d0f	ff		.
	rst 38h			;3d10	ff		.
	rst 38h			;3d11	ff		.
	rst 38h			;3d12	ff		.
	rst 38h			;3d13	ff		.
	rst 38h			;3d14	ff		.
	rst 38h			;3d15	ff		.
	rst 38h			;3d16	ff		.
	rst 38h			;3d17	ff		.
	rst 38h			;3d18	ff		.
	rst 38h			;3d19	ff		.
	rst 38h			;3d1a	ff		.
	rst 38h			;3d1b	ff		.
	rst 38h			;3d1c	ff		.
	rst 38h			;3d1d	ff		.
	rst 38h			;3d1e	ff		.
	rst 38h			;3d1f	ff		.
	rst 38h			;3d20	ff		.
	rst 38h			;3d21	ff		.
	rst 38h			;3d22	ff		.
	rst 38h			;3d23	ff		.
	rst 38h			;3d24	ff		.
	rst 38h			;3d25	ff		.
	rst 38h			;3d26	ff		.
	rst 38h			;3d27	ff		.
	rst 38h			;3d28	ff		.
	rst 38h			;3d29	ff		.
	rst 38h			;3d2a	ff		.
	rst 38h			;3d2b	ff		.
	rst 38h			;3d2c	ff		.
	rst 38h			;3d2d	ff		.
	rst 38h			;3d2e	ff		.
	rst 38h			;3d2f	ff		.
	rst 38h			;3d30	ff		.
	rst 38h			;3d31	ff		.
	rst 38h			;3d32	ff		.
	rst 38h			;3d33	ff		.
	rst 38h			;3d34	ff		.
	rst 38h			;3d35	ff		.
	rst 38h			;3d36	ff		.
	rst 38h			;3d37	ff		.
	rst 38h			;3d38	ff		.
	rst 38h			;3d39	ff		.
	rst 38h			;3d3a	ff		.
	rst 38h			;3d3b	ff		.
	rst 38h			;3d3c	ff		.
	rst 38h			;3d3d	ff		.
	rst 38h			;3d3e	ff		.
	rst 38h			;3d3f	ff		.
	rst 38h			;3d40	ff		.
	rst 38h			;3d41	ff		.
	rst 38h			;3d42	ff		.
	rst 38h			;3d43	ff		.
	rst 38h			;3d44	ff		.
	rst 38h			;3d45	ff		.
	rst 38h			;3d46	ff		.
	rst 38h			;3d47	ff		.
	rst 38h			;3d48	ff		.
	rst 38h			;3d49	ff		.
	rst 38h			;3d4a	ff		.
	rst 38h			;3d4b	ff		.
	rst 38h			;3d4c	ff		.
	rst 38h			;3d4d	ff		.
	rst 38h			;3d4e	ff		.
	rst 38h			;3d4f	ff		.
	rst 38h			;3d50	ff		.
	rst 38h			;3d51	ff		.
	rst 38h			;3d52	ff		.
	rst 38h			;3d53	ff		.
	rst 38h			;3d54	ff		.
	rst 38h			;3d55	ff		.
	rst 38h			;3d56	ff		.
	rst 38h			;3d57	ff		.
	rst 38h			;3d58	ff		.
	rst 38h			;3d59	ff		.
	rst 38h			;3d5a	ff		.
	rst 38h			;3d5b	ff		.
	rst 38h			;3d5c	ff		.
	rst 38h			;3d5d	ff		.
	rst 38h			;3d5e	ff		.
	rst 38h			;3d5f	ff		.
	rst 38h			;3d60	ff		.
	rst 38h			;3d61	ff		.
	rst 38h			;3d62	ff		.
	rst 38h			;3d63	ff		.
	rst 38h			;3d64	ff		.
	rst 38h			;3d65	ff		.
	rst 38h			;3d66	ff		.
	rst 38h			;3d67	ff		.
	rst 38h			;3d68	ff		.
	rst 38h			;3d69	ff		.
	rst 38h			;3d6a	ff		.
	rst 38h			;3d6b	ff		.
	rst 38h			;3d6c	ff		.
	rst 38h			;3d6d	ff		.
	rst 38h			;3d6e	ff		.
	rst 38h			;3d6f	ff		.
	rst 38h			;3d70	ff		.
	rst 38h			;3d71	ff		.
	rst 38h			;3d72	ff		.
	rst 38h			;3d73	ff		.
	rst 38h			;3d74	ff		.
	rst 38h			;3d75	ff		.
	rst 38h			;3d76	ff		.
	rst 38h			;3d77	ff		.
	rst 38h			;3d78	ff		.
	rst 38h			;3d79	ff		.
	rst 38h			;3d7a	ff		.
	rst 38h			;3d7b	ff		.
	rst 38h			;3d7c	ff		.
	rst 38h			;3d7d	ff		.
	rst 38h			;3d7e	ff		.
	rst 38h			;3d7f	ff		.
	rst 38h			;3d80	ff		.
	rst 38h			;3d81	ff		.
	rst 38h			;3d82	ff		.
	rst 38h			;3d83	ff		.
	rst 38h			;3d84	ff		.
	rst 38h			;3d85	ff		.
	rst 38h			;3d86	ff		.
	rst 38h			;3d87	ff		.
	rst 38h			;3d88	ff		.
	rst 38h			;3d89	ff		.
	rst 38h			;3d8a	ff		.
	rst 38h			;3d8b	ff		.
	rst 38h			;3d8c	ff		.
	rst 38h			;3d8d	ff		.
	rst 38h			;3d8e	ff		.
	rst 38h			;3d8f	ff		.
	rst 38h			;3d90	ff		.
	rst 38h			;3d91	ff		.
	rst 38h			;3d92	ff		.
	rst 38h			;3d93	ff		.
	rst 38h			;3d94	ff		.
	rst 38h			;3d95	ff		.
	rst 38h			;3d96	ff		.
	rst 38h			;3d97	ff		.
	rst 38h			;3d98	ff		.
	rst 38h			;3d99	ff		.
	rst 38h			;3d9a	ff		.
	rst 38h			;3d9b	ff		.
	rst 38h			;3d9c	ff		.
	rst 38h			;3d9d	ff		.
	rst 38h			;3d9e	ff		.
	rst 38h			;3d9f	ff		.
	rst 38h			;3da0	ff		.
	rst 38h			;3da1	ff		.
	rst 38h			;3da2	ff		.
	rst 38h			;3da3	ff		.
	rst 38h			;3da4	ff		.
	rst 38h			;3da5	ff		.
	rst 38h			;3da6	ff		.
	rst 38h			;3da7	ff		.
	rst 38h			;3da8	ff		.
	rst 38h			;3da9	ff		.
	rst 38h			;3daa	ff		.
	rst 38h			;3dab	ff		.
	rst 38h			;3dac	ff		.
	rst 38h			;3dad	ff		.
	rst 38h			;3dae	ff		.
	rst 38h			;3daf	ff		.
	rst 38h			;3db0	ff		.
	rst 38h			;3db1	ff		.
	rst 38h			;3db2	ff		.
	rst 38h			;3db3	ff		.
	rst 38h			;3db4	ff		.
	rst 38h			;3db5	ff		.
	rst 38h			;3db6	ff		.
	rst 38h			;3db7	ff		.
	rst 38h			;3db8	ff		.
	rst 38h			;3db9	ff		.
	rst 38h			;3dba	ff		.
	rst 38h			;3dbb	ff		.
	rst 38h			;3dbc	ff		.
	rst 38h			;3dbd	ff		.
	rst 38h			;3dbe	ff		.
	rst 38h			;3dbf	ff		.
	rst 38h			;3dc0	ff		.
	rst 38h			;3dc1	ff		.
	rst 38h			;3dc2	ff		.
	rst 38h			;3dc3	ff		.
	rst 38h			;3dc4	ff		.
	rst 38h			;3dc5	ff		.
	rst 38h			;3dc6	ff		.
	rst 38h			;3dc7	ff		.
	rst 38h			;3dc8	ff		.
	rst 38h			;3dc9	ff		.
	rst 38h			;3dca	ff		.
	rst 38h			;3dcb	ff		.
	rst 38h			;3dcc	ff		.
	rst 38h			;3dcd	ff		.
	rst 38h			;3dce	ff		.
	rst 38h			;3dcf	ff		.
	rst 38h			;3dd0	ff		.
	rst 38h			;3dd1	ff		.
	rst 38h			;3dd2	ff		.
	rst 38h			;3dd3	ff		.
	rst 38h			;3dd4	ff		.
	rst 38h			;3dd5	ff		.
	rst 38h			;3dd6	ff		.
	rst 38h			;3dd7	ff		.
	rst 38h			;3dd8	ff		.
	rst 38h			;3dd9	ff		.
	rst 38h			;3dda	ff		.
	rst 38h			;3ddb	ff		.
	rst 38h			;3ddc	ff		.
	rst 38h			;3ddd	ff		.
	rst 38h			;3dde	ff		.
	rst 38h			;3ddf	ff		.
	rst 38h			;3de0	ff		.
	rst 38h			;3de1	ff		.
	rst 38h			;3de2	ff		.
	rst 38h			;3de3	ff		.
	rst 38h			;3de4	ff		.
	rst 38h			;3de5	ff		.
	rst 38h			;3de6	ff		.
	rst 38h			;3de7	ff		.
	rst 38h			;3de8	ff		.
	rst 38h			;3de9	ff		.
	rst 38h			;3dea	ff		.
	rst 38h			;3deb	ff		.
	rst 38h			;3dec	ff		.
	rst 38h			;3ded	ff		.
	rst 38h			;3dee	ff		.
	rst 38h			;3def	ff		.
	rst 38h			;3df0	ff		.
	rst 38h			;3df1	ff		.
	rst 38h			;3df2	ff		.
	rst 38h			;3df3	ff		.
	rst 38h			;3df4	ff		.
	rst 38h			;3df5	ff		.
	rst 38h			;3df6	ff		.
	rst 38h			;3df7	ff		.
	rst 38h			;3df8	ff		.
	rst 38h			;3df9	ff		.
	rst 38h			;3dfa	ff		.
	rst 38h			;3dfb	ff		.
	rst 38h			;3dfc	ff		.
	rst 38h			;3dfd	ff		.
	rst 38h			;3dfe	ff		.
	rst 38h			;3dff	ff		.
	rst 38h			;3e00	ff		.
	rst 38h			;3e01	ff		.
	rst 38h			;3e02	ff		.
	rst 38h			;3e03	ff		.
	rst 38h			;3e04	ff		.
	rst 38h			;3e05	ff		.
	rst 38h			;3e06	ff		.
	rst 38h			;3e07	ff		.
	rst 38h			;3e08	ff		.
	rst 38h			;3e09	ff		.
	rst 38h			;3e0a	ff		.
	rst 38h			;3e0b	ff		.
	rst 38h			;3e0c	ff		.
	rst 38h			;3e0d	ff		.
	rst 38h			;3e0e	ff		.
	rst 38h			;3e0f	ff		.
	rst 38h			;3e10	ff		.
	rst 38h			;3e11	ff		.
	rst 38h			;3e12	ff		.
	rst 38h			;3e13	ff		.
	rst 38h			;3e14	ff		.
	rst 38h			;3e15	ff		.
	rst 38h			;3e16	ff		.
	rst 38h			;3e17	ff		.
	rst 38h			;3e18	ff		.
	rst 38h			;3e19	ff		.
	rst 38h			;3e1a	ff		.
	rst 38h			;3e1b	ff		.
	rst 38h			;3e1c	ff		.
	rst 38h			;3e1d	ff		.
	rst 38h			;3e1e	ff		.
	rst 38h			;3e1f	ff		.
	rst 38h			;3e20	ff		.
	rst 38h			;3e21	ff		.
	rst 38h			;3e22	ff		.
	rst 38h			;3e23	ff		.
	rst 38h			;3e24	ff		.
	rst 38h			;3e25	ff		.
	rst 38h			;3e26	ff		.
	rst 38h			;3e27	ff		.
	rst 38h			;3e28	ff		.
	rst 38h			;3e29	ff		.
	rst 38h			;3e2a	ff		.
	rst 38h			;3e2b	ff		.
	rst 38h			;3e2c	ff		.
	rst 38h			;3e2d	ff		.
	rst 38h			;3e2e	ff		.
	rst 38h			;3e2f	ff		.
	rst 38h			;3e30	ff		.
	rst 38h			;3e31	ff		.
	rst 38h			;3e32	ff		.
	rst 38h			;3e33	ff		.
	rst 38h			;3e34	ff		.
	rst 38h			;3e35	ff		.
	rst 38h			;3e36	ff		.
	rst 38h			;3e37	ff		.
	rst 38h			;3e38	ff		.
	rst 38h			;3e39	ff		.
	rst 38h			;3e3a	ff		.
	rst 38h			;3e3b	ff		.
	rst 38h			;3e3c	ff		.
	rst 38h			;3e3d	ff		.
	rst 38h			;3e3e	ff		.
	rst 38h			;3e3f	ff		.
	rst 38h			;3e40	ff		.
	rst 38h			;3e41	ff		.
	rst 38h			;3e42	ff		.
	rst 38h			;3e43	ff		.
	rst 38h			;3e44	ff		.
	rst 38h			;3e45	ff		.
	rst 38h			;3e46	ff		.
	rst 38h			;3e47	ff		.
	rst 38h			;3e48	ff		.
	rst 38h			;3e49	ff		.
	rst 38h			;3e4a	ff		.
	rst 38h			;3e4b	ff		.
	rst 38h			;3e4c	ff		.
	rst 38h			;3e4d	ff		.
	rst 38h			;3e4e	ff		.
	rst 38h			;3e4f	ff		.
	rst 38h			;3e50	ff		.
	rst 38h			;3e51	ff		.
	rst 38h			;3e52	ff		.
	rst 38h			;3e53	ff		.
	rst 38h			;3e54	ff		.
	rst 38h			;3e55	ff		.
	rst 38h			;3e56	ff		.
	rst 38h			;3e57	ff		.
	rst 38h			;3e58	ff		.
	rst 38h			;3e59	ff		.
	rst 38h			;3e5a	ff		.
	rst 38h			;3e5b	ff		.
	rst 38h			;3e5c	ff		.
	rst 38h			;3e5d	ff		.
	rst 38h			;3e5e	ff		.
	rst 38h			;3e5f	ff		.
	rst 38h			;3e60	ff		.
	rst 38h			;3e61	ff		.
	rst 38h			;3e62	ff		.
	rst 38h			;3e63	ff		.
	rst 38h			;3e64	ff		.
	rst 38h			;3e65	ff		.
	rst 38h			;3e66	ff		.
	rst 38h			;3e67	ff		.
	rst 38h			;3e68	ff		.
	rst 38h			;3e69	ff		.
	rst 38h			;3e6a	ff		.
	rst 38h			;3e6b	ff		.
	rst 38h			;3e6c	ff		.
	rst 38h			;3e6d	ff		.
	rst 38h			;3e6e	ff		.
	rst 38h			;3e6f	ff		.
	rst 38h			;3e70	ff		.
	rst 38h			;3e71	ff		.
	rst 38h			;3e72	ff		.
	rst 38h			;3e73	ff		.
	rst 38h			;3e74	ff		.
	rst 38h			;3e75	ff		.
	rst 38h			;3e76	ff		.
	rst 38h			;3e77	ff		.
	rst 38h			;3e78	ff		.
	rst 38h			;3e79	ff		.
	rst 38h			;3e7a	ff		.
	rst 38h			;3e7b	ff		.
	rst 38h			;3e7c	ff		.
	rst 38h			;3e7d	ff		.
	rst 38h			;3e7e	ff		.
	rst 38h			;3e7f	ff		.
	rst 38h			;3e80	ff		.
	rst 38h			;3e81	ff		.
	rst 38h			;3e82	ff		.
	rst 38h			;3e83	ff		.
	rst 38h			;3e84	ff		.
	rst 38h			;3e85	ff		.
	rst 38h			;3e86	ff		.
	rst 38h			;3e87	ff		.
	rst 38h			;3e88	ff		.
	rst 38h			;3e89	ff		.
	rst 38h			;3e8a	ff		.
	rst 38h			;3e8b	ff		.
	rst 38h			;3e8c	ff		.
	rst 38h			;3e8d	ff		.
	rst 38h			;3e8e	ff		.
	rst 38h			;3e8f	ff		.
	rst 38h			;3e90	ff		.
	rst 38h			;3e91	ff		.
	rst 38h			;3e92	ff		.
	rst 38h			;3e93	ff		.
	rst 38h			;3e94	ff		.
	rst 38h			;3e95	ff		.
	rst 38h			;3e96	ff		.
	rst 38h			;3e97	ff		.
	rst 38h			;3e98	ff		.
	rst 38h			;3e99	ff		.
	rst 38h			;3e9a	ff		.
	rst 38h			;3e9b	ff		.
	rst 38h			;3e9c	ff		.
	rst 38h			;3e9d	ff		.
	rst 38h			;3e9e	ff		.
	rst 38h			;3e9f	ff		.
	rst 38h			;3ea0	ff		.
	rst 38h			;3ea1	ff		.
	rst 38h			;3ea2	ff		.
	rst 38h			;3ea3	ff		.
	rst 38h			;3ea4	ff		.
	rst 38h			;3ea5	ff		.
	rst 38h			;3ea6	ff		.
	rst 38h			;3ea7	ff		.
	rst 38h			;3ea8	ff		.
	rst 38h			;3ea9	ff		.
	rst 38h			;3eaa	ff		.
	rst 38h			;3eab	ff		.
	rst 38h			;3eac	ff		.
	rst 38h			;3ead	ff		.
	rst 38h			;3eae	ff		.
	rst 38h			;3eaf	ff		.
	rst 38h			;3eb0	ff		.
	rst 38h			;3eb1	ff		.
	rst 38h			;3eb2	ff		.
	rst 38h			;3eb3	ff		.
	rst 38h			;3eb4	ff		.
	rst 38h			;3eb5	ff		.
	rst 38h			;3eb6	ff		.
	rst 38h			;3eb7	ff		.
	rst 38h			;3eb8	ff		.
	rst 38h			;3eb9	ff		.
	rst 38h			;3eba	ff		.
	rst 38h			;3ebb	ff		.
	rst 38h			;3ebc	ff		.
	rst 38h			;3ebd	ff		.
	rst 38h			;3ebe	ff		.
	rst 38h			;3ebf	ff		.
	rst 38h			;3ec0	ff		.
	rst 38h			;3ec1	ff		.
	rst 38h			;3ec2	ff		.
	rst 38h			;3ec3	ff		.
	rst 38h			;3ec4	ff		.
	rst 38h			;3ec5	ff		.
	rst 38h			;3ec6	ff		.
	rst 38h			;3ec7	ff		.
	rst 38h			;3ec8	ff		.
	rst 38h			;3ec9	ff		.
	rst 38h			;3eca	ff		.
	rst 38h			;3ecb	ff		.
	rst 38h			;3ecc	ff		.
	rst 38h			;3ecd	ff		.
	rst 38h			;3ece	ff		.
	rst 38h			;3ecf	ff		.
	rst 38h			;3ed0	ff		.
	rst 38h			;3ed1	ff		.
	rst 38h			;3ed2	ff		.
	rst 38h			;3ed3	ff		.
	rst 38h			;3ed4	ff		.
	rst 38h			;3ed5	ff		.
	rst 38h			;3ed6	ff		.
	rst 38h			;3ed7	ff		.
	rst 38h			;3ed8	ff		.
	rst 38h			;3ed9	ff		.
	rst 38h			;3eda	ff		.
	rst 38h			;3edb	ff		.
	rst 38h			;3edc	ff		.
	rst 38h			;3edd	ff		.
	rst 38h			;3ede	ff		.
	rst 38h			;3edf	ff		.
	rst 38h			;3ee0	ff		.
	rst 38h			;3ee1	ff		.
	rst 38h			;3ee2	ff		.
	rst 38h			;3ee3	ff		.
	rst 38h			;3ee4	ff		.
	rst 38h			;3ee5	ff		.
	rst 38h			;3ee6	ff		.
	rst 38h			;3ee7	ff		.
	rst 38h			;3ee8	ff		.
	rst 38h			;3ee9	ff		.
	rst 38h			;3eea	ff		.
	rst 38h			;3eeb	ff		.
	rst 38h			;3eec	ff		.
	rst 38h			;3eed	ff		.
	rst 38h			;3eee	ff		.
	rst 38h			;3eef	ff		.
	rst 38h			;3ef0	ff		.
	rst 38h			;3ef1	ff		.
	rst 38h			;3ef2	ff		.
	rst 38h			;3ef3	ff		.
	rst 38h			;3ef4	ff		.
	rst 38h			;3ef5	ff		.
	rst 38h			;3ef6	ff		.
	rst 38h			;3ef7	ff		.
	rst 38h			;3ef8	ff		.
	rst 38h			;3ef9	ff		.
	rst 38h			;3efa	ff		.
	rst 38h			;3efb	ff		.
	rst 38h			;3efc	ff		.
	rst 38h			;3efd	ff		.
	rst 38h			;3efe	ff		.
	rst 38h			;3eff	ff		.
	rst 38h			;3f00	ff		.
	rst 38h			;3f01	ff		.
	rst 38h			;3f02	ff		.
	rst 38h			;3f03	ff		.
	rst 38h			;3f04	ff		.
	rst 38h			;3f05	ff		.
	rst 38h			;3f06	ff		.
	rst 38h			;3f07	ff		.
	rst 38h			;3f08	ff		.
	rst 38h			;3f09	ff		.
	rst 38h			;3f0a	ff		.
	rst 38h			;3f0b	ff		.
	rst 38h			;3f0c	ff		.
	rst 38h			;3f0d	ff		.
	rst 38h			;3f0e	ff		.
	rst 38h			;3f0f	ff		.
	rst 38h			;3f10	ff		.
	rst 38h			;3f11	ff		.
	rst 38h			;3f12	ff		.
	rst 38h			;3f13	ff		.
	rst 38h			;3f14	ff		.
	rst 38h			;3f15	ff		.
	rst 38h			;3f16	ff		.
	rst 38h			;3f17	ff		.
	rst 38h			;3f18	ff		.
	rst 38h			;3f19	ff		.
	rst 38h			;3f1a	ff		.
	rst 38h			;3f1b	ff		.
	rst 38h			;3f1c	ff		.
	rst 38h			;3f1d	ff		.
	rst 38h			;3f1e	ff		.
	rst 38h			;3f1f	ff		.
	rst 38h			;3f20	ff		.
	rst 38h			;3f21	ff		.
	rst 38h			;3f22	ff		.
	rst 38h			;3f23	ff		.
	rst 38h			;3f24	ff		.
	rst 38h			;3f25	ff		.
	rst 38h			;3f26	ff		.
	rst 38h			;3f27	ff		.
	rst 38h			;3f28	ff		.
	rst 38h			;3f29	ff		.
	rst 38h			;3f2a	ff		.
	rst 38h			;3f2b	ff		.
	rst 38h			;3f2c	ff		.
	rst 38h			;3f2d	ff		.
	rst 38h			;3f2e	ff		.
	rst 38h			;3f2f	ff		.
	rst 38h			;3f30	ff		.
	rst 38h			;3f31	ff		.
	rst 38h			;3f32	ff		.
	rst 38h			;3f33	ff		.
	rst 38h			;3f34	ff		.
	rst 38h			;3f35	ff		.
	rst 38h			;3f36	ff		.
	rst 38h			;3f37	ff		.
	rst 38h			;3f38	ff		.
	rst 38h			;3f39	ff		.
	rst 38h			;3f3a	ff		.
	rst 38h			;3f3b	ff		.
	rst 38h			;3f3c	ff		.
	rst 38h			;3f3d	ff		.
	rst 38h			;3f3e	ff		.
	rst 38h			;3f3f	ff		.
	rst 38h			;3f40	ff		.
	rst 38h			;3f41	ff		.
	rst 38h			;3f42	ff		.
	rst 38h			;3f43	ff		.
	rst 38h			;3f44	ff		.
	rst 38h			;3f45	ff		.
	rst 38h			;3f46	ff		.
	rst 38h			;3f47	ff		.
	rst 38h			;3f48	ff		.
	rst 38h			;3f49	ff		.
	rst 38h			;3f4a	ff		.
	rst 38h			;3f4b	ff		.
	rst 38h			;3f4c	ff		.
	rst 38h			;3f4d	ff		.
	rst 38h			;3f4e	ff		.
	rst 38h			;3f4f	ff		.
	rst 38h			;3f50	ff		.
	rst 38h			;3f51	ff		.
	rst 38h			;3f52	ff		.
	rst 38h			;3f53	ff		.
	rst 38h			;3f54	ff		.
	rst 38h			;3f55	ff		.
	rst 38h			;3f56	ff		.
	rst 38h			;3f57	ff		.
	rst 38h			;3f58	ff		.
	rst 38h			;3f59	ff		.
	rst 38h			;3f5a	ff		.
	rst 38h			;3f5b	ff		.
	rst 38h			;3f5c	ff		.
	rst 38h			;3f5d	ff		.
	rst 38h			;3f5e	ff		.
	rst 38h			;3f5f	ff		.
	rst 38h			;3f60	ff		.
	rst 38h			;3f61	ff		.
	rst 38h			;3f62	ff		.
	rst 38h			;3f63	ff		.
	rst 38h			;3f64	ff		.
	rst 38h			;3f65	ff		.
	rst 38h			;3f66	ff		.
	rst 38h			;3f67	ff		.
	rst 38h			;3f68	ff		.
	rst 38h			;3f69	ff		.
	rst 38h			;3f6a	ff		.
	rst 38h			;3f6b	ff		.
	rst 38h			;3f6c	ff		.
	rst 38h			;3f6d	ff		.
	rst 38h			;3f6e	ff		.
	rst 38h			;3f6f	ff		.
	rst 38h			;3f70	ff		.
	rst 38h			;3f71	ff		.
	rst 38h			;3f72	ff		.
	rst 38h			;3f73	ff		.
	rst 38h			;3f74	ff		.
	rst 38h			;3f75	ff		.
	rst 38h			;3f76	ff		.
	rst 38h			;3f77	ff		.
	rst 38h			;3f78	ff		.
	rst 38h			;3f79	ff		.
	rst 38h			;3f7a	ff		.
	rst 38h			;3f7b	ff		.
	rst 38h			;3f7c	ff		.
	rst 38h			;3f7d	ff		.
	rst 38h			;3f7e	ff		.
	rst 38h			;3f7f	ff		.
	rst 38h			;3f80	ff		.
	rst 38h			;3f81	ff		.
	rst 38h			;3f82	ff		.
	rst 38h			;3f83	ff		.
	rst 38h			;3f84	ff		.
	rst 38h			;3f85	ff		.
	rst 38h			;3f86	ff		.
	rst 38h			;3f87	ff		.
	rst 38h			;3f88	ff		.
	rst 38h			;3f89	ff		.
	rst 38h			;3f8a	ff		.
	rst 38h			;3f8b	ff		.
	rst 38h			;3f8c	ff		.
	rst 38h			;3f8d	ff		.
	rst 38h			;3f8e	ff		.
	rst 38h			;3f8f	ff		.
	rst 38h			;3f90	ff		.
	rst 38h			;3f91	ff		.
	rst 38h			;3f92	ff		.
	rst 38h			;3f93	ff		.
	rst 38h			;3f94	ff		.
	rst 38h			;3f95	ff		.
	rst 38h			;3f96	ff		.
	rst 38h			;3f97	ff		.
	rst 38h			;3f98	ff		.
	rst 38h			;3f99	ff		.
	rst 38h			;3f9a	ff		.
	rst 38h			;3f9b	ff		.
	rst 38h			;3f9c	ff		.
	rst 38h			;3f9d	ff		.
	rst 38h			;3f9e	ff		.
	rst 38h			;3f9f	ff		.
	rst 38h			;3fa0	ff		.
	rst 38h			;3fa1	ff		.
	rst 38h			;3fa2	ff		.
	rst 38h			;3fa3	ff		.
	rst 38h			;3fa4	ff		.
	rst 38h			;3fa5	ff		.
	rst 38h			;3fa6	ff		.
	rst 38h			;3fa7	ff		.
	rst 38h			;3fa8	ff		.
	rst 38h			;3fa9	ff		.
	rst 38h			;3faa	ff		.
	rst 38h			;3fab	ff		.
	rst 38h			;3fac	ff		.
	rst 38h			;3fad	ff		.
	rst 38h			;3fae	ff		.
	rst 38h			;3faf	ff		.
	rst 38h			;3fb0	ff		.
	rst 38h			;3fb1	ff		.
	rst 38h			;3fb2	ff		.
	rst 38h			;3fb3	ff		.
	rst 38h			;3fb4	ff		.
	rst 38h			;3fb5	ff		.
	rst 38h			;3fb6	ff		.
	rst 38h			;3fb7	ff		.
	rst 38h			;3fb8	ff		.
	rst 38h			;3fb9	ff		.
	rst 38h			;3fba	ff		.
	rst 38h			;3fbb	ff		.
	rst 38h			;3fbc	ff		.
	rst 38h			;3fbd	ff		.
	rst 38h			;3fbe	ff		.
	rst 38h			;3fbf	ff		.
	rst 38h			;3fc0	ff		.
	rst 38h			;3fc1	ff		.
	rst 38h			;3fc2	ff		.
	rst 38h			;3fc3	ff		.
	rst 38h			;3fc4	ff		.
	rst 38h			;3fc5	ff		.
	rst 38h			;3fc6	ff		.
	rst 38h			;3fc7	ff		.
	rst 38h			;3fc8	ff		.
	rst 38h			;3fc9	ff		.
	rst 38h			;3fca	ff		.
	rst 38h			;3fcb	ff		.
	rst 38h			;3fcc	ff		.
	rst 38h			;3fcd	ff		.
	rst 38h			;3fce	ff		.
	rst 38h			;3fcf	ff		.
	rst 38h			;3fd0	ff		.
	rst 38h			;3fd1	ff		.
	rst 38h			;3fd2	ff		.
	rst 38h			;3fd3	ff		.
	rst 38h			;3fd4	ff		.
	rst 38h			;3fd5	ff		.
	rst 38h			;3fd6	ff		.
	rst 38h			;3fd7	ff		.
	rst 38h			;3fd8	ff		.
	rst 38h			;3fd9	ff		.
	rst 38h			;3fda	ff		.
	rst 38h			;3fdb	ff		.
	rst 38h			;3fdc	ff		.
	rst 38h			;3fdd	ff		.
	rst 38h			;3fde	ff		.
	rst 38h			;3fdf	ff		.
	rst 38h			;3fe0	ff		.
	rst 38h			;3fe1	ff		.
	rst 38h			;3fe2	ff		.
	rst 38h			;3fe3	ff		.
	rst 38h			;3fe4	ff		.
	rst 38h			;3fe5	ff		.
	rst 38h			;3fe6	ff		.
	rst 38h			;3fe7	ff		.
	rst 38h			;3fe8	ff		.
	rst 38h			;3fe9	ff		.
	rst 38h			;3fea	ff		.
	rst 38h			;3feb	ff		.
	rst 38h			;3fec	ff		.
	rst 38h			;3fed	ff		.
	rst 38h			;3fee	ff		.
	rst 38h			;3fef	ff		.
	rst 38h			;3ff0	ff		.
	rst 38h			;3ff1	ff		.
	rst 38h			;3ff2	ff		.
	rst 38h			;3ff3	ff		.
	rst 38h			;3ff4	ff		.
	rst 38h			;3ff5	ff		.
	rst 38h			;3ff6	ff		.
	rst 38h			;3ff7	ff		.
	rst 38h			;3ff8	ff		.
	rst 38h			;3ff9	ff		.
	rst 38h			;3ffa	ff		.
	rst 38h			;3ffb	ff		.
	rst 38h			;3ffc	ff		.
	rst 38h			;3ffd	ff		.
	rst 38h			;3ffe	ff		.
	rst 38h			;3fff	ff		.
