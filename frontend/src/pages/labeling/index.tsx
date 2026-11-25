import { LabelingPageView } from "./components/labeling-page-view";
import { useLabelPage } from "./hooks/use-label-page";

/** 打单发货（原打单台 + 发货台）：只做装配。 */
export default function LabelingPage() {
  return <LabelingPageView page={useLabelPage()} />;
}
