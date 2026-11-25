import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SegmentedControl from './segmented-control';

const options = [{ value: 'a', label: '顺序' }, { value: 'b', label: '随机' }];

describe('切换条字段名', () => {
  it('默认不显示字段名，只给读屏', () => {
    render(<SegmentedControl options={options} value="a" onValueChange={() => {}} label="话术顺序" />);
    expect(screen.queryByText('话术顺序')).toBeNull();
    expect(screen.getByRole('group', { name: '话术顺序' })).toBeTruthy();
  });
  it('showLabel 时字段名显示在上方', () => {
    render(<SegmentedControl options={options} value="a" onValueChange={() => {}} label="话术顺序" showLabel />);
    expect(screen.getByText('话术顺序')).toBeTruthy();
  });
});
