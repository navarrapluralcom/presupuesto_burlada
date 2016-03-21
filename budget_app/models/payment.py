from django.db import models, connection

from django.conf import settings

MAX_RESULTS = 10000

class PaymentManager(models.Manager):
    # Return the list of payees
    def get_payees(self, entity_id):
        return self.values_list('payee', flat=True) \
                    .filter(budget_id__entity=entity_id) \
                    .distinct() \
                    .order_by('payee')

    # Return the list of areas
    def get_areas(self, entity_id):
        return self.values_list('area', flat=True) \
                    .filter(budget_id__entity=entity_id) \
                    .distinct() \
                    .order_by('area')

    # Return a list of years for which we have payments
    def get_years(self, entity_id):
        return self.values_list('budget_id__year', flat=True) \
                    .filter(budget_id__entity=entity_id) \
                    .distinct() \
                    .order_by('budget__year')

    # Return the list of payees.
    # Unfortunately we couldn't find a way to bend the Django aggregate functions to do this,
    # and raw() needs the primary key to be in the result list, so we end up having to
    # access the DB connection directly. :/
    def get_biggest_payees(self, entity, limit):
        sql = \
            "select " \
                "p.payee, sum(p.amount) " \
            "from " \
                "payments p " \
                "left join budgets b on p.budget_id = b.id " \
            "where " \
                "b.entity_id = "+str(entity.id)+" " \
            "group by payee " \
            "order by sum(amount) desc " \
            "limit " + str(limit)
        cursor = connection.cursor()
        cursor.execute(sql)
        return list(cursor.fetchall())

    def each_denormalized(self, additional_constraints=None, additional_arguments=None):
        # XXX: Note that this left join syntax works well even when the economic_category_id is null,
        # as opposed to the way we query for Budget Items. I should probably adopt this all around,
        # and potentially even stop using dummy categories on loaders.
        sql = \
            "select " \
                "p.id, p.area, p.programme, p.date, p.payee, p.expense, p.amount, p.description, " \
                "coalesce(ec.description, 'Otros') as ec_description, " \
                "b.year " \
            "from " \
                "payments p " \
                "left join budgets b on p.budget_id = b.id " \
                "left join economic_categories ec on p.economic_category_id = ec.id "

        if additional_constraints:
            sql += " where " + additional_constraints

        sql += " limit "+str(MAX_RESULTS)

        return self.raw(sql, additional_arguments)

    # Do a full-text search in the database
    def search(self, query, year, language):
        sql = "select " \
            "b.year, " \
            "e.name, e.level, " \
            "fc.programme, fc.description as fc_description, " \
            "p.id, p.area, p.date, p.description, p.amount, p.expense " \
          "from " \
            "payments p " \
                "left join budgets b on p.budget_id = b.id " \
                "left join entities e on b.entity_id = e.id " \
                "left join functional_categories fc on p.functional_category_id = fc.id " \
          "where " \
            "e.language='"+language+"' and " \
            "to_tsvector('"+settings.SEARCH_CONFIG+"',p.payee||' '||p.description) @@ plainto_tsquery('"+settings.SEARCH_CONFIG+"',%s)"
        if year:
            sql += " and b.year='%s'" % year
        sql += " order by p.amount desc"
        return self.raw(sql, (query, ))


class Payment(models.Model):
    budget = models.ForeignKey('Budget')
    area = models.CharField(max_length=100, null=True)
    programme = models.CharField(max_length=100, null=True)
    functional_category = models.ForeignKey('FunctionalCategory', db_column='functional_category_id', null=True)
    economic_category = models.ForeignKey('EconomicCategory', db_column='economic_category_id', null=True)
    economic_concept = models.CharField(max_length=10, null=True)
    date = models.DateField(null=True)
    contract_type = models.CharField(max_length=50, null=True)
    payee = models.CharField(max_length=200)
    description = models.CharField(max_length=300)
    expense = models.BooleanField()
    amount = models.BigIntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PaymentManager()

    class Meta:
        app_label = "budget_app"
        db_table = "payments"

    def __unicode__(self):
        return self.payee
