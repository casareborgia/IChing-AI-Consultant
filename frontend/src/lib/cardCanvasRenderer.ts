import { JournalSummary } from '../types/iching';

export interface RenderCardResult {
  dataUrl: string;
  blob: Blob;
  fileName: string;
}

/**
 * 내담자의 상담 저널 데이터를 바탕으로 고해상도(1080x1520) 마음 전념 카드를 브라우저 Canvas로 렌더링합니다.
 */
export function renderCardCanvas(journal: JournalSummary): RenderCardResult {
  const isCrisis = Boolean(journal.isCrisis);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Canvas 2D context를 초기화할 수 없습니다.');
  }

  const width = 1080;
  const height = 1520;
  canvas.width = width;
  canvas.height = height;

  // 1. 배경 그라데이션
  const bgGradient = ctx.createLinearGradient(0, 0, width, height);
  if (isCrisis) {
    bgGradient.addColorStop(0, '#2b0c10');
    bgGradient.addColorStop(0.5, '#120507');
    bgGradient.addColorStop(1, '#2b0c10');
  } else {
    bgGradient.addColorStop(0, '#1c1917'); // stone-900
    bgGradient.addColorStop(0.5, '#0c0a09'); // stone-950
    bgGradient.addColorStop(1, '#1c1917');
  }
  ctx.fillStyle = bgGradient;
  ctx.fillRect(0, 0, width, height);

  // 2. 외곽 테두리
  ctx.strokeStyle = isCrisis ? '#e11d48' : '#d97706'; // rose-600 / amber-600
  ctx.lineWidth = 4;
  ctx.strokeRect(40, 40, width - 80, height - 80);

  // 3. 내부 섬세선
  ctx.strokeStyle = isCrisis ? '#4c0519' : '#451a03';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(55, 55, width - 110, height - 110);

  // 4. 모서리 액센트
  const cornerSize = 25;
  ctx.strokeStyle = isCrisis ? '#fb7185' : '#fbbf24';
  ctx.lineWidth = 3;

  const corners = [
    [55, 55 + cornerSize, 55, 55, 55 + cornerSize, 55],
    [width - 55 - cornerSize, 55, width - 55, 55, width - 55, 55 + cornerSize],
    [55, height - 55 - cornerSize, 55, height - 55, 55 + cornerSize, height - 55],
    [width - 55 - cornerSize, height - 55, width - 55, height - 55, width - 55, height - 55 - cornerSize],
  ];

  corners.forEach(([x1, y1, x2, y2, x3, y3]) => {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.lineTo(x3, y3);
    ctx.stroke();
  });

  // 5. 헤더 타이틀
  ctx.textAlign = 'center';
  ctx.fillStyle = isCrisis ? '#f43f5e' : '#f59e0b';
  ctx.font = 'bold 44px sans-serif';
  ctx.fillText(isCrisis ? '긴급 마음 안심 카드' : '마음 전념 카드', width / 2, 130);

  // 6. 소제목 및 구분선
  ctx.fillStyle = '#a8a29e';
  ctx.font = '24px sans-serif';
  ctx.fillText(
    isCrisis
      ? '생명과 안정을 지키는 Stanley-Brown 안전계획'
      : '지행합일(知行合一) : 오늘의 알아차림을 내일의 행동으로',
    width / 2,
    180
  );

  ctx.strokeStyle = isCrisis ? '#881337' : '#78350f';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(90, 215);
  ctx.lineTo(width - 90, 215);
  ctx.stroke();

  // 7. 본문 섹션 렌더링
  let currentY = 270;
  const renderSection = (title: string, content: string, isHighlight = false) => {
    const boxWidth = width - 180;
    const boxPadding = 25;
    const maxTextWidth = boxWidth - (boxPadding * 2);

    ctx.font = '22px sans-serif';
    const lines: string[] = [];
    const paragraphs = content.split('\n');

    paragraphs.forEach((p) => {
      if (!p.trim()) return;
      let line = '';
      for (let i = 0; i < p.length; i++) {
        const testLine = line + p[i];
        const metrics = ctx.measureText(testLine);
        if (metrics.width > maxTextWidth && i > 0) {
          lines.push(line);
          line = p[i];
        } else {
          line = testLine;
        }
      }
      if (line) lines.push(line);
    });

    const lineHeight = 34;
    const boxHeight = Math.max(90, (lines.length * lineHeight) + 65);

    // 섹션 배경
    ctx.fillStyle = isHighlight
      ? (isCrisis ? 'rgba(136, 19, 55, 0.4)' : 'rgba(120, 53, 15, 0.35)')
      : 'rgba(28, 25, 23, 0.6)';
    ctx.fillRect(90, currentY - 30, boxWidth, boxHeight);

    ctx.strokeStyle = isHighlight
      ? (isCrisis ? '#f43f5e' : '#f59e0b')
      : (isCrisis ? '#4c0519' : '#292524');
    ctx.lineWidth = isHighlight ? 2 : 1;
    ctx.strokeRect(90, currentY - 30, boxWidth, boxHeight);

    // 라벨
    ctx.textAlign = 'left';
    ctx.fillStyle = isHighlight
      ? (isCrisis ? '#fb7185' : '#fbbf24')
      : (isCrisis ? '#fda4af' : '#d97706');
    ctx.font = 'bold 24px sans-serif';
    ctx.fillText(title, 90 + boxPadding, currentY);

    // 텍스트 출력
    ctx.fillStyle = isHighlight
      ? (isCrisis ? '#ffe4e6' : '#fef3c7')
      : '#e7e5e4';

    for (let j = 0; j < lines.length; j++) {
      ctx.fillText(lines[j].trim(), 90 + boxPadding, currentY + (j * lineHeight) + 12);
    }

    currentY += boxHeight + 35;
  };

  renderSection('象 여정의 궤적', journal.clarifiedQuestion || '주역 괘를 통한 성찰');
  renderSection('吉 성찰을 붙드는 기둥', journal.hexagramSummary || '본괘의 지혜');

  const insightsList = Array.isArray(journal.keyInsights) ? journal.keyInsights : [];
  if (insightsList.length > 0) {
    renderSection('省 성찰의 눈뜸과 지지', insightsList.join('\n\n'));
  }

  renderSection('行 오늘 나의 전념 행동', journal.suggestedAction || '작은 실천을 행합니다.', true);

  // 8. 하단 워터마크
  ctx.textAlign = 'center';
  ctx.fillStyle = '#78716c';
  ctx.font = '22px sans-serif';
  ctx.fillText('주역 심층 AI 상담 · I-Ching Oracle', width / 2, height - 70);

  // 9. 이미지 Data URL 및 동기식 바이너리 Blob 변환
  const dataUrl = canvas.toDataURL('image/png');
  const byteString = atob(dataUrl.split(',')[1]);
  const mimeString = dataUrl.split(',')[0].split(':')[1].split(';')[0];
  const ab = new ArrayBuffer(byteString.length);
  const ia = new Uint8Array(ab);
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i);
  }
  const blob = new Blob([ab], { type: mimeString });
  const fileName = `Action_Commitment_Card_${new Date().toISOString().slice(0, 10)}.png`;

  return { dataUrl, blob, fileName };
}
