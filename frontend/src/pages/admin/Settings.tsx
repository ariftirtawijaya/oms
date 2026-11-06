import { PageHeader } from "@/components/common";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BrandingTab } from "@/components/settings/BrandingTab";
import { CleanupTab } from "@/components/settings/CleanupTab";

export default function SettingsPage() {
  return (
    <div className="space-y-5 fade-up" data-testid="settings-page">
      <PageHeader title="Pengaturan" />
      <Tabs defaultValue="branding">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="branding" data-testid="settings-tab-branding">Branding Aplikasi</TabsTrigger>
          <TabsTrigger value="cleanup" data-testid="settings-tab-cleanup">Pembersihan Data</TabsTrigger>
        </TabsList>
        <TabsContent value="branding" className="mt-4"><BrandingTab /></TabsContent>
        <TabsContent value="cleanup" className="mt-4"><CleanupTab /></TabsContent>
      </Tabs>
    </div>
  );
}
