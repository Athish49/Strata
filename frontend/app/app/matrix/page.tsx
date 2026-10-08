import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { MatrixView } from "@/components/matrix/MatrixView";

export default function Page() {
  return (
    <PageContainer full>
      <PageHeader title="Impact matrix" caption="Which documents each changed rule touches" />
      <MatrixView />
    </PageContainer>
  );
}
