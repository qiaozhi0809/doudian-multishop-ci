import styles from "../labeling-page.module.css";

/** 原因清单：Arc Alert 的内容放在 <p> 里，不能用 ul，只能用 span 搭。 */
export function ReasonList({ items }: { items: { key: string | number; text: string }[] }) {
  return (
    <span className={styles.reasonList} role="list">
      {items.map((item) => (
        <span key={item.key} role="listitem">
          {item.text}
        </span>
      ))}
    </span>
  );
}
