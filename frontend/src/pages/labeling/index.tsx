import { LabelingPageView } from "./components/labeling-page-view";
import { useLabelPage } from "./hooks/use-label-page";

/** 打单台：只做装配。 */
export default function LabelingPage() {
  return <LabelingPageView page={useLabelPage()} />;
}
