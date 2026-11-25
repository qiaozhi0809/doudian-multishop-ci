import type { components } from "@/lib/api-types";
import styles from "../shop-page.module.css";

type BaseData = components["schemas"]["BaseData"];

function Section({ title, empty, children }: { title: string; empty: boolean; children: React.ReactNode }) {
  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{title}</h3>
      {empty ? <p className={styles.muted}>暂无</p> : <ul className={styles.list}>{children}</ul>}
    </section>
  );
}

function Item({ main, sub, end }: { main: string; sub?: string | null; end?: string }) {
  return (
    <li className={styles.listItem}>
      <span className={styles.listMain}>
        <span>{main}</span>
        {sub ? <span className={styles.muted}>{sub}</span> : null}
      </span>
      {end ? <span className={styles.numeric}>{end}</span> : null}
    </li>
  );
}

const orEmpty = (v: string | null | undefined) => v || "暂无";

/** 本店基础数据：发货地址、快递、面单模板、面单账户（只读）。 */
export function BaseDataSections({ data }: { data: BaseData }) {
  return (
    <>
      <Section title="发货地址" empty={data.addresses.length === 0}>
        {data.addresses.map((a) => (
          <Item key={a.address_id} main={orEmpty(a.name)} sub={`${orEmpty(a.region)} ${a.phone ?? ""}`.trim()} end={a.is_default ? "默认" : undefined} />
        ))}
      </Section>
      <Section title="快递" empty={data.couriers.length === 0}>
        {data.couriers.map((c) => (
          <Item key={c.courier_code} main={orEmpty(c.name)} sub={c.courier_code} />
        ))}
      </Section>
      <Section title="面单模板" empty={data.templates.length === 0}>
        {data.templates.map((t) => (
          <Item key={t.template_code} main={orEmpty(t.name)} sub={t.courier_code} end={t.is_custom ? "自定义" : undefined} />
        ))}
      </Section>
      <Section title="面单账户" empty={data.accounts.length === 0}>
        {data.accounts.map((a) => (
          <Item
            key={a.ebill_id}
            main={orEmpty(a.net_name)}
            sub={a.courier_code}
            end={`${a.is_default ? "默认 · " : ""}余额 ${a.balance ?? "暂无"}`}
          />
        ))}
      </Section>
    </>
  );
}
