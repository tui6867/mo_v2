import type { CSSProperties } from 'react';

const paths = {
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  diagonal: 'M6 18 18 6M6 6h12v12',
  check: 'm5 12 4 4L19 6',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5',
  file: 'M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 13h8M8 17h5',
  shield: 'M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4Zm-5 9 3 3 7-7',
  edit: 'm15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z',
  mail: 'M3 5h18v14H3V5Zm0 1 9 8 9-8',
  send: 'm3 3 19 9-19 9 4-9-4-9Zm4 9h15',
  replay: 'M4 9a8 8 0 1 1 0 7M4 3v6h6',
  close: 'm6 6 12 12M6 18 18 6',
  pause: 'M8 5v14M16 5v14',
  play: 'm7 4 14 8-14 8V4Z',
  plus: 'M12 5v14M5 12h14',
  link: 'm10 13 4-4M8 16l-2 2a4 4 0 0 1-5-5l5-5a4 4 0 0 1 5 0m2 0 2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-5 0',
  lock: 'M6 10h12v11H6V10Zm3 0V6a3 3 0 0 1 6 0v4',
} as const;
export type IconName = keyof typeof paths;
export function Icon({ name, className = '', style }: { name: IconName; className?: string; style?: CSSProperties }) {
  return <svg className={`icon ${className}`} style={style} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

export function BrandMark() {
  return <svg className="brand-mark" width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M4 23V9l12 9L28 9v14M4 9l12 9L28 9" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" /></svg>;
}
