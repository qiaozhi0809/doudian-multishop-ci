import { KpiDot } from "@/lib/kpi-tone";
import {
  ASIDE_HEADLINE,
  ASIDE_LEAD,
  FEATURE_GROUPS,
  PREVIEW_TILES,
  START_STEPS,
} from "../logic/auth-aside-content";
import styles from "../auth-aside.module.css";

/** 登录页右侧内容区：一句话介绍、经营概览示意、按侧栏分组的功能、快速开始。 */
export function AuthAside() {
  return (
    <div className={styles.aside}>
      <div className={styles.intro}>
        <h2 className={styles.title}>{ASIDE_HEADLINE}</h2>
        <p className={styles.lead}>{ASIDE_LEAD}</p>
      </div>

      <div className={styles.preview} aria-hidden="true">
        <p className={styles.previewLabel}>经营概览</p>
        <div className={styles.previewRow}>
          {PREVIEW_TILES.map((tile) => (
            <div key={tile.name} className={styles.previewCell}>
              <span className={styles.previewName}>
                <KpiDot tone={tile.tone} value={1} />
                {tile.name}
              </span>
              <span className={styles.previewValue}>{tile.value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.groups} role="list" aria-label="主要功能">
        {FEATURE_GROUPS.map((group) => (
          <section key={group.name} className={styles.group} role="listitem" aria-label={group.name}>
            <h3 className={styles.groupName}>{group.name}</h3>
            <ul className={styles.features}>
              {group.items.map(({ name, text }) => (
                <li key={name} className={styles.feature}>
                  <span className={styles.featureName}>{name}</span>
                  <span className={styles.featureText}>{text}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <div className={styles.steps}>
        <h3 className={styles.stepsTitle}>快速开始</h3>
        <ol className={styles.stepList}>
          {START_STEPS.map((step, index) => (
            <li key={step.name} className={styles.step}>
              <span className={styles.stepNo} aria-hidden="true">
                {index + 1}
              </span>
              <span className={styles.stepName}>{step.name}</span>
              <span className={styles.stepText}>{step.text}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
