import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Plus } from 'lucide-react';
import { Button } from './button';

describe('Button loading', () => {
  it('keeps the label visible and puts the spinner inside the label slot, left of the text', () => {
    render(<Button loading>提交克隆</Button>);
    const btn = screen.getByRole('button', { name: '提交克隆' });
    expect(btn.getAttribute('aria-busy')).toBe('true');
    expect(btn.textContent).toContain('提交克隆');
    const spinner = btn.querySelector('[class*="spinner"]');
    expect(spinner).toBeTruthy();
    const slot = btn.querySelector('[class*="labelSlot"]')!;
    expect(slot.contains(spinner)).toBe(true);
    expect(slot.firstElementChild?.className).toMatch(/loader/);
  });

  it('icon-only: spinner shows while the icon is still in the DOM (CSS fades it)', () => {
    render(<Button loading iconOnly aria-label="添加"><Plus /></Button>);
    const btn = screen.getByRole('button', { name: '添加' });
    expect(btn.querySelector('[class*="spinner"]')).toBeTruthy();
    expect(btn.className).toMatch(/iconOnly/);
  });

  it('no spinner when not loading', () => {
    render(<Button>保存</Button>);
    expect(screen.getByRole('button').querySelector('[class*="spinner"]')).toBeNull();
  });
});
