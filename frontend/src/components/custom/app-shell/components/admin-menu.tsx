import { DropdownMenu } from "@/components/arc/dropdown-menu/dropdown-menu";

interface AdminMenuProps {
  username: string;
  onChangePassword: () => void;
  onLogout: () => void;
}

/** 当前管理员菜单：修改密码、退出。 */
export function AdminMenu({ username, onChangePassword, onLogout }: AdminMenuProps) {
  return (
    <DropdownMenu
      label={username}
      items={[
        { label: "修改密码", onSelect: onChangePassword },
        { label: "退出", onSelect: onLogout, separatorBefore: true },
      ]}
    />
  );
}
