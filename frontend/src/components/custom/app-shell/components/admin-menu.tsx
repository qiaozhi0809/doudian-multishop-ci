import { KeyRound } from "lucide-react";
import { UserMenu } from "@/components/custom/user-menu/user-menu";
import { useTheme } from "@/lib/theme";

interface AdminMenuProps {
  username: string;
  onChangePassword: () => void;
  onLogout: () => void;
}

/** 左下角个人中心：头像 + 管理员名；菜单里切主题、修改密码、退出登录。 */
export function AdminMenu({ username, onChangePassword, onLogout }: AdminMenuProps) {
  const [theme, setTheme] = useTheme();
  return (
    <UserMenu
      name={username}
      initial={username.slice(0, 1).toUpperCase()}
      theme={theme}
      onThemeChange={setTheme}
      items={[{ label: "修改密码", icon: <KeyRound size={16} strokeWidth={1.75} />, onSelect: onChangePassword }]}
      onSignOut={onLogout}
    />
  );
}
