import { forwardRef, type ReactNode } from 'react';
import * as Menu from '@radix-ui/react-dropdown-menu';
import { ChevronsUpDown, LogOut, Monitor, Moon, Sun, UserRound } from 'lucide-react';
import menuStyles from '@/components/arc/dropdown-menu/dropdown-menu.module.css';
import Tooltip from '@/components/arc/tooltip/tooltip';
import type { ThemePreference } from '@/lib/theme';
import styles from './user-menu.module.css';

export interface UserMenuItem {
  label: string;
  icon?: ReactNode;
  onSelect: () => void;
}

export interface UserMenuProps {
  /** 显示名。 */
  name: string;
  /** 头像上的字；没有昵称时传空，改显示人形图标。 */
  initial?: string;
  /** 名字下面的灰色小字，例如「剩余 12 天 · 已绑定」。 */
  summary?: string;
  /** 打码后的手机号，只显示在菜单顶部。 */
  phone?: string;
  items: UserMenuItem[];
  theme: ThemePreference;
  onThemeChange: (theme: ThemePreference) => void;
  /** 不传则不显示「退出登录」（例如本机授权，没有账号可退）。 */
  onSignOut?: () => void;
  /** 菜单弹出方向。放在左下角用 top（默认）。 */
  side?: 'top' | 'bottom';
}

/** 主题按钮每点一下按这个顺序换；设置页「界面」里仍是三段全称选择。 */
const THEME_ORDER: ThemePreference[] = ['light', 'dark', 'system'];
const THEME_NAME: Record<ThemePreference, string> = { light: '浅色', dark: '深色', system: '跟随系统' };
const THEME_ICON: Record<ThemePreference, typeof Sun> = { light: Sun, dark: Moon, system: Monitor };

function AvatarMark({ initial }: { initial?: string }) {
  return (
    <span className={styles.avatar} aria-hidden="true">
      {initial ? initial : <UserRound size={16} strokeWidth={1.75} />}
    </span>
  );
}

/** 账号块：不加悬停提示（它本身就写着名字，规则：只有纯图标按钮才加提示）。 */
const Trigger = forwardRef<HTMLButtonElement, { name: string; initial?: string; summary?: string }>(function Trigger({ name, initial, summary, ...rest }, ref) {
  return (
    <button ref={ref} type="button" className={styles.trigger} aria-label={`账号菜单，${name}`} {...rest}>
      <AvatarMark initial={initial} />
      <span className={styles.who}>
        <span className={styles.name}>{name}</span>
        {summary ? <span className={styles.summary}>{summary}</span> : null}
      </span>
      <ChevronsUpDown size={14} aria-hidden="true" className={styles.chev} />
    </button>
  );
});

/** 主题图标按钮：放在菜单顶部账号信息右边，点一下换到下一个主题，菜单不关。是菜单项，键盘上下键也能走到。 */
function ThemeButton({ theme, onThemeChange }: { theme: ThemePreference; onThemeChange: (theme: ThemePreference) => void }) {
  const next = THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length];
  const Icon = THEME_ICON[theme];
  const tip = `主题：${THEME_NAME[theme]}，点一下换成${THEME_NAME[next]}`;
  return (
    <Tooltip content={tip}>
      <Menu.Item className={styles.themeButton} aria-label={tip} onSelect={(event) => { event.preventDefault(); onThemeChange(next); }}>
        <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
      </Menu.Item>
    </Tooltip>
  );
}

/** 侧栏左下角的账号菜单：头像 + 两行纯文字；菜单顶部是账号信息（右边一个主题图标按钮），接着账号链接、退出登录。菜单宽度跟随账号块。 */
export function UserMenu({ name, initial, summary, phone, items, theme, onThemeChange, onSignOut, side = 'top' }: UserMenuProps) {
  return (
    <Menu.Root>
      <Menu.Trigger asChild>
        <Trigger name={name} initial={initial} summary={summary} />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content className={`${menuStyles.content} ${styles.panel}`} side={side} align="start" sideOffset={8} collisionPadding={12}>
          <div className={styles.headRow}>
            <div className={styles.head}>
              <span className={styles.headName}>{name}</span>
              {phone ? <span className={styles.headMeta}>{phone}</span> : null}
              {summary ? <span className={styles.headMeta}>{summary}</span> : null}
            </div>
            <ThemeButton theme={theme} onThemeChange={onThemeChange} />
          </div>
          <Menu.Separator className={menuStyles.separator} />
          {items.map((item) => (
            <Menu.Item key={item.label} className={menuStyles.item} onSelect={item.onSelect}>
              {item.icon ? <span aria-hidden="true" style={{ display: 'inline-flex' }}>{item.icon}</span> : null}
              <span>{item.label}</span>
            </Menu.Item>
          ))}
          {onSignOut ? (
            <>
              <Menu.Separator className={menuStyles.separator} />
              <Menu.Item className={menuStyles.item} onSelect={onSignOut}>
                <span aria-hidden="true" style={{ display: 'inline-flex' }}><LogOut size={16} strokeWidth={1.75} /></span>
                <span>退出登录</span>
              </Menu.Item>
            </>
          ) : null}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

export default UserMenu;
