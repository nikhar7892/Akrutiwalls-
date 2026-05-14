import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { saveIdentity } from "@/app/actions/company";

export const dynamic = "force-dynamic";

export default async function IdentityPage() {
  const { company: ctx } = await requireActiveCompany();
  const company = await prisma.company.findUnique({ where: { id: ctx.id } });
  if (!company) return null;

  return (
    <div className="max-w-3xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Identity</h1>
        <p className="text-sm text-slate-500">Statutory identifiers and company classification.</p>
      </header>

      <form action={saveIdentity} className="card grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Company name" name="name" defaultValue={company.name} required />
        <Field label="CIN" name="cin" defaultValue={company.cin} required />
        <Field label="PAN" name="pan" defaultValue={company.pan ?? ""} />
        <Field label="TAN" name="tan" defaultValue={company.tan ?? ""} />
        <Field label="GSTIN" name="gstin" defaultValue={company.gstin ?? ""} />
        <Field label="ROC Code" name="rocCode" defaultValue={company.rocCode ?? ""} />
        <Field
          label="Registration No."
          name="registrationNo"
          defaultValue={company.registrationNo ?? ""}
        />
        <Field
          label="Date of Incorporation"
          name="dateOfIncorporation"
          type="date"
          defaultValue={company.dateOfIncorporation?.toISOString().slice(0, 10) ?? ""}
        />
        <Field label="Official Email" name="emailOfficial" type="email" defaultValue={company.emailOfficial ?? ""} />
        <Field label="Official Phone" name="phoneOfficial" defaultValue={company.phoneOfficial ?? ""} />
        <Field label="Website" name="website" defaultValue={company.website ?? ""} />

        <Select
          label="Class"
          name="companyClass"
          defaultValue={company.companyClass}
          options={["PRIVATE", "PUBLIC", "OPC", "LLP", "SECTION_8"]}
        />
        <Select
          label="Status"
          name="status"
          defaultValue={company.status}
          options={["ACTIVE", "DORMANT", "STRIKE_OFF", "UNDER_LIQUIDATION", "DISSOLVED", "AMALGAMATED"]}
        />
        <Select
          label="Listing"
          name="listingStatus"
          defaultValue={company.listingStatus}
          options={["UNLISTED", "LISTED"]}
        />
        <Field label="Main NIC Code" name="mainNicCode" defaultValue={company.mainNicCode ?? ""} />
        <div className="sm:col-span-2">
          <label className="label">Business Nature</label>
          <textarea
            className="input"
            name="businessNature"
            rows={3}
            defaultValue={company.businessNature ?? ""}
          />
        </div>
        <div className="sm:col-span-2">
          <button className="btn" type="submit">Save identity</button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label, name, defaultValue, type = "text", required = false,
}: { label: string; name: string; defaultValue?: string; type?: string; required?: boolean }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input className="input" name={name} type={type} defaultValue={defaultValue} required={required} />
    </div>
  );
}
function Select({
  label, name, defaultValue, options,
}: { label: string; name: string; defaultValue: string; options: string[] }) {
  return (
    <div>
      <label className="label">{label}</label>
      <select className="input" name={name} defaultValue={defaultValue}>
        {options.map((o) => (
          <option key={o} value={o}>{o.replaceAll("_", " ")}</option>
        ))}
      </select>
    </div>
  );
}
