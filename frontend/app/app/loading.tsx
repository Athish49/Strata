import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/shell/PageHeader";

export default function Loading() {
  return (
    <PageContainer>
      <Skeleton className="mb-2 h-4 w-40" />
      <Skeleton className="mb-8 h-11 w-96" />
      <Skeleton className="h-14 w-full rounded-[12px]" />
      <div className="mt-6 grid grid-cols-2 gap-6">
        <Skeleton className="h-64 rounded-[12px]" />
        <Skeleton className="h-64 rounded-[12px]" />
      </div>
    </PageContainer>
  );
}
