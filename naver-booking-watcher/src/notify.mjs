import nodemailer from 'nodemailer';

export async function sendAvailabilityEmail({ to, matches }) {
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;
  if (!user || !pass) {
    console.warn('[notify] SMTP_USER / SMTP_PASS 환경변수가 없어 이메일을 보내지 않고 콘솔에만 출력합니다.');
    for (const m of matches) console.log(`[빈자리] ${m.target} ${m.date} ${m.time} -> ${m.url}`);
    return;
  }

  const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: { user, pass },
  });

  const lines = matches.map(
    (m) => `- ${m.target} / ${m.date} ${m.time}\n  예약 페이지(직접 클릭해서 예약해주세요): ${m.url}`
  );

  await transporter.sendMail({
    from: user,
    to,
    subject: `[네이버예약 알림] 빈자리 ${matches.length}건 발견`,
    text: [
      '조건에 맞는 빈자리를 찾았어요! 이 도구는 알림만 보내며, 예약 페이지를 자동으로 열거나 예약을 대신 진행하지 않습니다.',
      '아래 링크를 직접 눌러서 예약을 완료해주세요.',
      '',
      ...lines,
    ].join('\n'),
  });
}
